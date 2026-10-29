#!/usr/bin/env python3
"""Automated corpus expansion and ingestion for Sahkar-Saathi.

This maintenance script:
1. Scans `data/raw/` for all PDF files.
2. Validates magic bytes (%PDF-) to detect HTML error pages or corrupted downloads.
3. Automatically updates `data/sources.csv`:
   - Sets `use_in_corpus = 'Y'` for valid PDFs.
   - Sets `use_in_corpus = 'N'` for invalid/corrupted files or missing PDFs.
   - Fixes local_path if previously pointing to a stale extension (e.g., .html).
   - Appends clean new rows for valid PDFs that are not yet in `sources.csv`.
4. Synchronizes PostgreSQL metadata using `python manage.py load_sources`.
5. Executes corpus ingestion using `docker-compose exec web python manage.py ingest_corpus`.
6. Reports the final tally of successfully ingested documents, chunks added, and vector points upserted.

Usage:
    python scripts/expand_corpus.py
    python scripts/expand_corpus.py --skip-ingest
    python scripts/expand_corpus.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

if sys.platform == "win32":
    # Ensure UTF-8 console output on Windows to prevent UnicodeEncodeError/UnicodeDecodeError
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
DEFAULT_SOURCES_CSV = ROOT / "data" / "sources.csv"

PDF_MAGIC = b"%PDF-"


@dataclass
class PDFInspectionResult:
    filename: str
    path: pathlib.Path
    is_valid: bool
    size_bytes: int
    header_preview: bytes
    error_reason: str = ""


def inspect_raw_pdfs(raw_dir: pathlib.Path) -> list[PDFInspectionResult]:
    """Inspect all *.pdf files in the raw directory for valid PDF magic bytes."""
    results: list[PDFInspectionResult] = []
    if not raw_dir.is_dir():
        print(f"[!] Warning: Raw directory does not exist: {raw_dir}")
        return results

    pdf_files = sorted(raw_dir.glob("*.pdf"))
    for file_path in pdf_files:
        size = file_path.stat().st_size
        header = b""
        is_valid = False
        error_reason = ""

        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header.startswith(PDF_MAGIC):
                is_valid = True
            elif b"<html" in header.lower() or b"<!doctype" in header.lower():
                is_valid = False
                error_reason = "HTML web page saved as PDF"
            elif size == 0:
                is_valid = False
                error_reason = "Empty file (0 bytes)"
            else:
                is_valid = False
                error_reason = f"Invalid magic bytes ({header[:8]!r})"
        except OSError as exc:
            is_valid = False
            error_reason = f"Read error: {exc}"

        results.append(
            PDFInspectionResult(
                filename=file_path.name,
                path=file_path,
                is_valid=is_valid,
                size_bytes=size,
                header_preview=header,
                error_reason=error_reason,
            )
        )

    return results


def find_matching_row_index(
    fname: str,
    rel_path: str,
    sources: list[dict[str, str]],
) -> int | None:
    """Find the index of the row matching a raw PDF file in sources.csv."""
    # 1. Match by exact normalized local_path
    for idx, r in enumerate(sources):
        r_path = r.get("local_path", "").replace("\\", "/").strip()
        if r_path == rel_path:
            return idx

    stem = fname.removesuffix(".pdf")

    # 2. Match by exact doc_id equal to filename stem
    for idx, r in enumerate(sources):
        if r.get("doc_id", "").strip() == stem:
            return idx

    # 3. Match by doc_id stripping language suffix (e.g. CEN-CRCS-FAQ from CEN-CRCS-FAQ_en)
    if "_" in stem:
        cand_id = stem.rsplit("_", 1)[0]
        for idx, r in enumerate(sources):
            if r.get("doc_id", "").strip() == cand_id:
                return idx

    # 4. Match prefix
    for idx, r in enumerate(sources):
        did = r.get("doc_id", "").strip()
        if did and fname.startswith(did):
            return idx

    return None


def generate_new_row(doc_id: str, local_path: str, filename: str) -> dict[str, str]:
    """Synthesize a complete sources.csv row for an unlisted valid PDF."""
    lang = "en"
    if "_" in filename:
        parts = filename.removesuffix(".pdf").rsplit("_", 1)
        if len(parts) == 2 and len(parts[1]) in (2, 3):
            lang = parts[1]

    upper_id = doc_id.upper()
    state = "TN" if upper_id.startswith("TN-") else "central"

    doc_type = "scheme-guideline"
    if "-ACT-" in upper_id or upper_id.endswith("-ACT"):
        doc_type = "act"
    elif "-RULES-" in upper_id or upper_id.endswith("-RULES"):
        doc_type = "rules"
    elif "-BYLAWS" in upper_id or "-BYE-LAWS" in upper_id:
        doc_type = "model-bylaws"
    elif "-CIRCULAR-" in upper_id or "-DIR-" in upper_id:
        doc_type = "circular"

    clean_title = doc_id.replace("-", " ").title()

    if state == "TN":
        publisher = "Co-operation, Food and Consumer Protection Department, Government of Tamil Nadu"
    elif "RBI" in upper_id:
        publisher = "Reserve Bank of India"
    else:
        publisher = "Ministry of Cooperation, Government of India"

    today_str = datetime.date.today().isoformat()
    return {
        "doc_id": doc_id,
        "title": clean_title,
        "publisher": publisher,
        "doc_type": doc_type,
        "source_url": "",
        "published_date": "",
        "enacted_date": "",
        "language": lang,
        "state": state,
        "version": "1",
        "status": "active",
        "licence": "Not stated in document; check site terms of use",
        "accessed_date": today_str,
        "local_path": local_path,
        "scanned": "N",
        "use_in_corpus": "Y",
        "priority": "Medium",
        "verification": "AUTO_INGESTED",
        "notes": f"Auto-discovered and added by expand_corpus.py on {today_str}",
    }


def update_sources_csv(
    sources_csv_path: pathlib.Path,
    inspections: list[PDFInspectionResult],
    root_dir: pathlib.Path,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Synchronize inspected PDFs with sources.csv.

    Returns:
        (updated_count, appended_count, unchanged_count)
    """
    if not sources_csv_path.is_file():
        raise FileNotFoundError(f"sources.csv not found at: {sources_csv_path}")

    with open(sources_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        sources = list(reader)

    matched_indices: set[int] = set()
    updated_count = 0
    appended_count = 0
    unchanged_count = 0

    print("\n" + "=" * 80)
    print("STEP 1: INSPECTION & SOURCES.CSV RECONCILIATION")
    print("=" * 80)

    for item in inspections:
        rel_path = f"data/raw/{item.filename}"
        row_idx = find_matching_row_index(item.filename, rel_path, sources)

        if row_idx is not None:
            matched_indices.add(row_idx)
            row = sources[row_idx]
            doc_id = row.get("doc_id", "UNKNOWN")
            old_use = row.get("use_in_corpus", "")
            old_path = row.get("local_path", "")
            target_use = "Y" if item.is_valid else "N"

            needs_update = False
            changes = []

            if old_use != target_use:
                row["use_in_corpus"] = target_use
                needs_update = True
                changes.append(f"use_in_corpus: '{old_use}' -> '{target_use}'")

            # If it's a valid PDF and the existing path had .html or mismatched filename, fix it
            if item.is_valid and old_path != rel_path:
                row["local_path"] = rel_path
                needs_update = True
                changes.append(f"local_path: '{old_path}' -> '{rel_path}'")

            if needs_update:
                updated_count += 1
                status_label = "[VALID PDF]" if item.is_valid else f"[INVALID: {item.error_reason}]"
                print(f"  * UPDATED  | {doc_id:<32} {status_label:<32} | {', '.join(changes)}")
            else:
                unchanged_count += 1
                status_label = "[VALID PDF]" if item.is_valid else f"[INVALID: {item.error_reason}]"
                print(f"  - NO CHANGE| {doc_id:<32} {status_label:<32} | use_in_corpus={old_use}")

        else:
            # File exists in data/raw/ but is missing from sources.csv
            if item.is_valid:
                stem = item.filename.removesuffix(".pdf")
                new_doc_id = stem.rsplit("_", 1)[0] if "_" in stem else stem
                new_row = generate_new_row(new_doc_id, rel_path, item.filename)
                sources.append(new_row)
                matched_indices.add(len(sources) - 1)
                appended_count += 1
                print(f"  + APPENDED | {new_doc_id:<32} [NEW VALID PDF]               | Added row with use_in_corpus='Y'")
            else:
                print(f"  ! SKIPPED  | {item.filename:<32} [UNMATCHED & INVALID]          | {item.error_reason}")

    # Also verify existing rows that were NOT in data/raw: if file is missing, ensure use_in_corpus='N'
    for idx, row in enumerate(sources):
        if idx not in matched_indices:
            doc_id = row.get("doc_id", "")
            local_path = row.get("local_path", "").strip()
            cur_use = row.get("use_in_corpus", "")
            full_path = root_dir / local_path if local_path else None
            exists = full_path.is_file() if full_path else False

            if not exists and cur_use == "Y":
                row["use_in_corpus"] = "N"
                updated_count += 1
                print(f"  * UPDATED  | {doc_id:<32} [MISSING FILE]                  | use_in_corpus: 'Y' -> 'N'")

    print("-" * 80)
    print(f"Summary: {updated_count} updated, {appended_count} newly added, {unchanged_count} unchanged.")

    if not dry_run and (updated_count > 0 or appended_count > 0):
        with open(sources_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(sources)
        print(f"[OK] Saved updated sources to: {sources_csv_path}")
    elif dry_run:
        print("[i] Dry-run enabled: sources.csv was not modified.")

    return updated_count, appended_count, unchanged_count


def get_docker_compose_command() -> list[str]:
    """Detect available docker compose command (prefer docker-compose if present)."""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    return ["docker-compose"]


def run_command_streaming(cmd: list[str], description: str) -> tuple[int, list[str]]:
    """Run a subprocess command and stream output lines to the console."""
    print(f"\n[>] Executing: {' '.join(cmd)}")
    print(f"[>] {description}...\n")

    lines: list[str] = []
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    if process.stdout:
        for line in process.stdout:
            print(line, end="")
            lines.append(line.rstrip("\r\n"))

    process.wait()
    return process.returncode, lines


def run_corpus_expansion_pipeline(
    raw_dir: pathlib.Path = DEFAULT_RAW_DIR,
    sources_csv_path: pathlib.Path = DEFAULT_SOURCES_CSV,
    skip_ingest: bool = False,
    dry_run: bool = False,
) -> int:
    """Execute the full automated corpus expansion pipeline."""
    print("\n========================================================")
    print(" Sahkar-Saathi: Corpus Expansion & Ingestion Automation")
    print("========================================================")

    # Step 1 & 2: Scan and inspect PDFs
    inspections = inspect_raw_pdfs(raw_dir)
    valid_count = sum(1 for i in inspections if i.is_valid)
    invalid_count = len(inspections) - valid_count
    print(f"\nFound {len(inspections)} PDF files in {raw_dir}:")
    print(f"  * Valid readable PDFs:   {valid_count}")
    print(f"  * Corrupted / HTML error: {invalid_count}")

    # Step 3: Update sources.csv
    update_sources_csv(sources_csv_path, inspections, ROOT, dry_run=dry_run)

    if skip_ingest or dry_run:
        print("\n[i] Ingestion skipped as requested (--skip-ingest or --dry-run).")
        return 0

    compose_cmd = get_docker_compose_command()

    # Step 4a: Synchronize PostgreSQL documents metadata
    print("\n" + "=" * 80)
    print("STEP 2: SYNC POSTGRESQL DOCUMENT METADATA (load_sources)")
    print("=" * 80)
    load_cmd = compose_cmd + ["exec", "-T", "web", "python", "manage.py", "load_sources"]
    rc_load, _ = run_command_streaming(load_cmd, "Syncing metadata with load_sources")
    if rc_load != 0:
        print(f"[!] Warning: load_sources exited with return code {rc_load}.")

    # Step 4b: Execute corpus ingestion
    print("\n" + "=" * 80)
    print("STEP 3: EXECUTE CORPUS INGESTION (ingest_corpus)")
    print("=" * 80)
    ingest_cmd = compose_cmd + ["exec", "-T", "web", "python", "manage.py", "ingest_corpus"]
    rc_ingest, ingest_output = run_command_streaming(ingest_cmd, "Ingesting corpus and seeding Qdrant vectors")

    # Step 5: Report final tally
    print("\n" + "=" * 80)
    print("STEP 4: FINAL CORPUS EXPANSION TALLY")
    print("=" * 80)

    ingested_docs: list[str] = []
    total_chunks = 0
    total_vectors = 0

    for line in ingest_output:
        # Match chunks saved: "Saved 157 chunks to PostgreSQL for CEN-MSCS-ACT-2023."
        chunk_match = re.search(r"Saved\s+(\d+)\s+chunks\s+to\s+PostgreSQL\s+for\s+([A-Za-z0-9\-_]+)", line)
        if chunk_match:
            chunks = int(chunk_match.group(1))
            doc_id = chunk_match.group(2)
            ingested_docs.append(doc_id)
            total_chunks += chunks

        vec_match = re.search(r"Upserted\s+(\d+)\s+vectors\s+to\s+Qdrant", line)
        if vec_match:
            total_vectors += int(vec_match.group(1))

    print(f"Documents Ingested:        {len(ingested_docs)}")
    print(f"Total Chunks Saved to DB:  {total_chunks}")
    print(f"Total Vectors in Qdrant:   {total_vectors}")
    print(f"Ingest Command Status:     {'SUCCESS (Exit code 0)' if rc_ingest == 0 else f'FAILED (Exit code {rc_ingest})'}")

    if ingested_docs:
        print("\nBreakdown of Ingested Documents:")
        for idx, doc_id in enumerate(ingested_docs, 1):
            print(f"  {idx:02d}. {doc_id}")

    print("=" * 80 + "\n")
    return rc_ingest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automate Sahkar-Saathi corpus expansion and ingestion."
    )
    parser.add_argument(
        "--raw-dir",
        type=pathlib.Path,
        default=DEFAULT_RAW_DIR,
        help="Path to data/raw/ directory",
    )
    parser.add_argument(
        "--sources-csv",
        type=pathlib.Path,
        default=DEFAULT_SOURCES_CSV,
        help="Path to data/sources.csv",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Only update sources.csv, skip Docker ingestion command",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect files and report updates without modifying sources.csv or running ingestion",
    )

    args = parser.parse_args()
    rc = run_corpus_expansion_pipeline(
        raw_dir=args.raw_dir,
        sources_csv_path=args.sources_csv,
        skip_ingest=args.skip_ingest,
        dry_run=args.dry_run,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
