#!/usr/bin/env python3
"""Check data/raw/ against data/sources.csv, and optionally ingest the corpus.

    python scripts/expand_corpus.py                    # report only: nothing is changed
    python scripts/expand_corpus.py --write            # also update data/sources.csv
    python scripts/expand_corpus.py --write --demote-missing
    python scripts/expand_corpus.py --write --skip-ingest
    python scripts/expand_corpus.py --dry-run          # report only, never ingests

By default the script only reports. It scans data/raw/*.pdf, checks that each file starts
with the PDF signature (%PDF-), and compares that with sources.csv:

- A use_in_corpus=Y row whose PDF is missing or invalid is only REPORTED. It is changed to N
  only with --write --demote-missing, because a PDF missing on one machine (git ignores
  data/raw) must not remove a document from the corpus for everyone.
- A valid PDF with no row in sources.csv is reported, and with --write appended as a new
  row (use_in_corpus=Y, verification=AUTO_INGESTED) for a person to complete.
- A valid PDF whose row has a different local_path (a stale .html name, say) is reported,
  and with --write the path is corrected. use_in_corpus is never promoted to Y here: Y,
  Hold and N are a person's decision.

Without --write or with --dry-run, sources.csv is not touched. With --write, after the
CSV is updated, the script runs `load_sources` and `ingest_corpus` in the `web` service of
docker-compose.yml (`docker compose exec -T web ...`), unless --skip-ingest is given, and
reports the documents, chunks and vectors written.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
DEFAULT_SOURCES_CSV = ROOT / "data" / "sources.csv"

PDF_MAGIC = b"%PDF-"
COMPOSE_SERVICE = "web"  # the Django container in docker-compose.yml
TN_PUBLISHER = "Co-operation, Food and Consumer Protection Department, Government of Tamil Nadu"


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

    for file_path in sorted(raw_dir.glob("*.pdf")):
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
                error_reason = "HTML web page saved as PDF"
            elif size == 0:
                error_reason = "Empty file (0 bytes)"
            else:
                error_reason = f"Invalid magic bytes ({header[:8]!r})"
        except OSError as exc:
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

    if state == "TN":
        publisher = TN_PUBLISHER
    elif "RBI" in upper_id:
        publisher = "Reserve Bank of India"
    else:
        publisher = "Ministry of Cooperation, Government of India"

    today_str = datetime.date.today().isoformat()
    return {
        "doc_id": doc_id,
        "title": doc_id.replace("-", " ").title(),
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
    write: bool = False,
    demote_missing: bool = False,
) -> tuple[int, int, int]:
    """Compare the inspected PDFs with sources.csv; change the file only if ``write``.

    A Y row with a missing or invalid PDF is changed to N only if ``demote_missing`` is also
    set; otherwise it is only reported. Returns (updated, appended, unchanged).
    """
    if not sources_csv_path.is_file():
        raise FileNotFoundError(f"sources.csv not found at: {sources_csv_path}")

    with open(sources_csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        sources = list(reader)

    matched_indices: set[int] = set()
    updated_count = 0
    appended_count = 0
    unchanged_count = 0
    problem_count = 0
    verb = "WOULD UPDATE" if not write else "UPDATED"

    print("\n" + "=" * 80)
    print("STEP 1: INSPECTION & SOURCES.CSV RECONCILIATION")
    print("=" * 80)

    for item in inspections:
        rel_path = f"data/raw/{item.filename}"
        row_idx = find_matching_row_index(item.filename, rel_path, sources)
        label = "[VALID PDF]" if item.is_valid else f"[INVALID: {item.error_reason}]"

        if row_idx is None:
            # File exists in data/raw/ but is missing from sources.csv
            if item.is_valid:
                stem = item.filename.removesuffix(".pdf")
                new_doc_id = stem.rsplit("_", 1)[0] if "_" in stem else stem
                sources.append(generate_new_row(new_doc_id, rel_path, item.filename))
                matched_indices.add(len(sources) - 1)
                appended_count += 1
                print(
                    f"  + {'ADD' if not write else 'ADDED':<12}| {new_doc_id:<32} [NEW VALID PDF]"
                )
            else:
                print(
                    f"  ! SKIPPED    | {item.filename:<32} [UNMATCHED, INVALID] {item.error_reason}"
                )
            continue

        matched_indices.add(row_idx)
        row = sources[row_idx]
        doc_id = row.get("doc_id", "UNKNOWN")
        old_use = row.get("use_in_corpus", "")
        old_path = row.get("local_path", "")
        changes = []

        # A valid PDF whose row points elsewhere (for example a stale .html name).
        if item.is_valid and old_path != rel_path:
            row["local_path"] = rel_path
            changes.append(f"local_path: '{old_path}' -> '{rel_path}'")

        if not item.is_valid and old_use == "Y":
            problem_count += 1
            if demote_missing:
                row["use_in_corpus"] = "N"
                changes.append("use_in_corpus: 'Y' -> 'N'")
            else:
                print(
                    f"  ! PROBLEM    | {doc_id:<32} {label} (still Y; --demote-missing to change)"
                )
        elif item.is_valid and old_use != "Y":
            print(f"  ? SUGGEST    | {doc_id:<32} valid PDF but use_in_corpus={old_use!r}")

        if changes:
            updated_count += 1
            print(f"  * {verb:<10} | {doc_id:<32} {label} | {', '.join(changes)}")
        else:
            unchanged_count += 1

    # Y rows whose file is not in data/raw/ at all (git ignores data/raw, so this is common).
    for idx, row in enumerate(sources):
        if idx in matched_indices or row.get("use_in_corpus", "") != "Y":
            continue
        local_path = row.get("local_path", "").strip()
        if local_path and (root_dir / local_path).is_file():
            continue
        problem_count += 1
        doc_id = row.get("doc_id", "")
        if demote_missing:
            row["use_in_corpus"] = "N"
            updated_count += 1
            print(f"  * {verb:<10} | {doc_id:<32} [MISSING FILE] | use_in_corpus: 'Y' -> 'N'")
        else:
            print(f"  ! PROBLEM    | {doc_id:<32} [MISSING FILE] {local_path} (still Y)")

    print("-" * 80)
    print(
        f"Summary: {updated_count} to update, {appended_count} to add, {unchanged_count} "
        f"unchanged, {problem_count} Y row(s) with a missing or invalid PDF."
    )

    if write and (updated_count > 0 or appended_count > 0):
        with open(sources_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(sources)
        print(f"[OK] Saved updated sources to: {sources_csv_path}")
    else:
        print("[i] Report only: sources.csv was not modified (use --write to update it).")

    return updated_count, appended_count, unchanged_count


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


def tally(ingest_output: list[str]) -> tuple[list[str], int, int]:
    """(documents, chunks, vectors) reported by ingest_corpus."""
    docs: list[str] = []
    chunks = 0
    vectors = 0
    for line in ingest_output:
        # "Saved 157 chunks to PostgreSQL for CEN-MSCS-ACT-2023."
        saved = re.search(r"Saved\s+(\d+)\s+chunks\s+to\s+PostgreSQL\s+for\s+([\w\-]+)", line)
        if saved:
            chunks += int(saved.group(1))
            docs.append(saved.group(2))
        upserted = re.search(r"Upserted\s+(\d+)\s+vectors\s+to\s+Qdrant", line)
        if upserted:
            vectors += int(upserted.group(1))
    return docs, chunks, vectors


def run_corpus_expansion_pipeline(
    raw_dir: pathlib.Path = DEFAULT_RAW_DIR,
    sources_csv_path: pathlib.Path = DEFAULT_SOURCES_CSV,
    skip_ingest: bool = False,
    dry_run: bool = False,
    write: bool = False,
    demote_missing: bool = False,
) -> int:
    """Report on the corpus files; with --write update sources.csv and ingest."""
    print("\n========================================================")
    print(" Sahkar-Saathi: Corpus Check & Ingestion")
    print("========================================================")

    inspections = inspect_raw_pdfs(raw_dir)
    valid_count = sum(1 for i in inspections if i.is_valid)
    print(f"\nFound {len(inspections)} PDF files in {raw_dir}:")
    print(f"  * Valid readable PDFs:   {valid_count}")
    print(f"  * Corrupted / HTML error: {len(inspections) - valid_count}")

    write = write and not dry_run
    update_sources_csv(
        sources_csv_path, inspections, ROOT, write=write, demote_missing=demote_missing
    )

    if not write or skip_ingest:
        print("\n[i] Ingestion skipped (it runs only with --write, and not with --skip-ingest).")
        return 0

    compose = ["docker", "compose", "exec", "-T", COMPOSE_SERVICE, "python", "manage.py"]

    print("\n" + "=" * 80)
    print("STEP 2: SYNC POSTGRESQL DOCUMENT METADATA (load_sources)")
    print("=" * 80)
    rc_load, _ = run_command_streaming(compose + ["load_sources"], "Syncing with load_sources")
    if rc_load != 0:
        print(f"[!] Warning: load_sources exited with return code {rc_load}.")

    print("\n" + "=" * 80)
    print("STEP 3: EXECUTE CORPUS INGESTION (ingest_corpus)")
    print("=" * 80)
    rc_ingest, ingest_output = run_command_streaming(
        compose + ["ingest_corpus"], "Ingesting corpus and seeding Qdrant vectors"
    )

    print("\n" + "=" * 80)
    print("STEP 4: FINAL CORPUS TALLY")
    print("=" * 80)
    docs, total_chunks, total_vectors = tally(ingest_output)
    status = "SUCCESS (Exit code 0)" if rc_ingest == 0 else f"FAILED (Exit code {rc_ingest})"
    print(f"Documents Ingested:        {len(docs)}")
    print(f"Total Chunks Saved to DB:  {total_chunks}")
    print(f"Total Vectors in Qdrant:   {total_vectors}")
    print(f"Ingest Command Status:     {status}")
    for idx, doc_id in enumerate(docs, 1):
        print(f"  {idx:02d}. {doc_id}")
    print("=" * 80 + "\n")
    return rc_ingest


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        # UTF-8 console output on Windows, so non-ASCII text cannot raise UnicodeEncodeError.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Check data/raw/ against sources.csv (report only unless --write)."
    )
    parser.add_argument("--raw-dir", type=pathlib.Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--sources-csv", type=pathlib.Path, default=DEFAULT_SOURCES_CSV)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update sources.csv (path fixes, new rows), then run load_sources and ingest_corpus",
    )
    parser.add_argument(
        "--demote-missing",
        action="store_true",
        help="With --write, set use_in_corpus Y -> N for rows whose PDF is missing or invalid",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="With --write, only update sources.csv; do not run the Docker commands",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, even with --write: change nothing and ingest nothing",
    )

    args = parser.parse_args(argv)
    return run_corpus_expansion_pipeline(
        raw_dir=args.raw_dir,
        sources_csv_path=args.sources_csv,
        skip_ingest=args.skip_ingest,
        dry_run=args.dry_run,
        write=args.write,
        demote_missing=args.demote_missing,
    )


if __name__ == "__main__":
    sys.exit(main())
