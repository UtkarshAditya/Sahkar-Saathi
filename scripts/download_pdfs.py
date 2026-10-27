#!/usr/bin/env python3
"""Download the source PDFs listed in data/sources.csv into data/raw/.

    python scripts/download_pdfs.py                # TLS certificates are verified
    python scripts/download_pdfs.py --only-corpus  # only rows with use_in_corpus=Y
    python scripts/download_pdfs.py --missing      # download nothing; list what is missing
    python scripts/download_pdfs.py --insecure     # skips verification: see the warning below

Only rows whose local_path ends in .pdf and whose source_url is a direct PDF link are
downloaded. Files that already start with the PDF signature are kept, so it is safe to
re-run. The PDFs the script cannot fetch (web pages, not files) come from the team Drive,
or are printed to PDF from the browser by hand.

`data/raw/*` is git-ignored, but some PDFs are tracked (added with `git add -f`); a new
PDF needs `git add -f` to be shared through git.

`--missing` is a report: no network, no file written. It lists every row that should have a
PDF in data/raw/ but does not, with why (no file, a file whose name differs only in case,
a file that is not a PDF) and how to get it. File names are compared exactly, as they are
in the Linux container, even on Windows where the file system ignores case.

Standard library only. Exits 1 if any download failed.
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import ssl
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 30

# Some government sites block the default Python user agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}


def is_valid_pdf(path: pathlib.Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(4) == b"%PDF"


def is_direct_pdf_link(url: str) -> bool:
    return bool(url) and ".pdf" in url.lower().split("?")[0]


def in_corpus(row: dict) -> bool:
    """use_in_corpus is Y, Hold or N; only Y is ingested."""
    return (row.get("use_in_corpus") or "").strip().upper() == "Y"


def tls_context(insecure: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if insecure:
        bar = "!" * 72
        print(
            f"{bar}\nWARNING: --insecure turns OFF TLS certificate verification.\n"
            "Anyone on the network path could substitute these documents. Use it only for a\n"
            "site you already know has a broken certificate, and check the files afterwards.\n"
            f"{bar}",
            file=sys.stderr,
            flush=True,
        )
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


# --- --missing: a report of what the corpus lacks ---------------------------------------


def problem_with(raw_dir: pathlib.Path, name: str) -> str | None:
    """Why `name` is not a usable PDF in raw_dir, or None if it is one. The name is matched
    exactly, from the directory listing, so a wrong-case name is caught on Windows too."""
    names = os.listdir(raw_dir) if raw_dir.is_dir() else []
    if name in names:
        return None if is_valid_pdf(raw_dir / name) else "file is not a PDF"
    differs = [n for n in names if n.lower() == name.lower()]
    if differs:
        return f"named {differs[0]!r} (case differs)"
    return "no file"


def how_to_get(url: str) -> str:
    if is_direct_pdf_link(url):
        return "direct PDF link"
    if url:
        return "web page: print to PDF by hand"
    return "no URL: get it from the Drive"


def report_missing(rows: list[dict], raw_dir: pathlib.Path) -> int:
    gaps = []
    expected = 0
    for row in rows:
        local_path = (row.get("local_path") or "").strip()
        if not local_path:
            continue
        expected += 1
        name = pathlib.PurePath(local_path).name
        problem = problem_with(raw_dir, name)
        if problem:
            url = (row.get("source_url") or "").strip()
            corpus = (row.get("use_in_corpus") or "").strip() or "-"
            gaps.append((row["doc_id"], corpus, problem, how_to_get(url), local_path, url))

    if not gaps:
        print(f"Every one of the {expected} expected files is in {raw_dir}.")
        return 0

    header = ("doc_id", "corpus", "problem", "how to get it", "local_path", "source_url")
    widths = [max(len(header[i]), *(len(g[i]) for g in gaps)) for i in range(5)]
    print(f"{len(gaps)} of {expected} expected files are missing or unusable in {raw_dir}:\n")
    for line in (header, *gaps):
        cells = [line[i].ljust(widths[i]) for i in range(5)]
        print("  ".join(cells) + "  " + line[5])
    direct = sum(g[3] == "direct PDF link" for g in gaps)
    in_y = sum(g[1].upper() == "Y" for g in gaps)
    print(
        f"\n{in_y} of them have use_in_corpus=Y. {direct} have a direct PDF link "
        "(python scripts/download_pdfs.py); the rest must be printed to PDF or fetched by hand."
    )
    odd = [g[0] for g in gaps if not g[4].lower().endswith(".pdf")]
    if odd:
        print(
            f"{len(odd)} row(s) have a local_path that is not a .pdf ({', '.join(odd)}); "
            "ingest_corpus reads PDFs only, so the CSV owner should point them at a PDF."
        )
    return 0


# --- Downloading ------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the source PDFs into data/raw/.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Do not verify TLS certificates (unsafe; for sites with a broken certificate).",
    )
    parser.add_argument(
        "--only-corpus",
        action="store_true",
        help="Only rows with use_in_corpus=Y (the ones ingest_corpus reads).",
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Download nothing: list the rows that should have a PDF in data/raw/ but do not.",
    )
    parser.add_argument(
        "--sources",
        type=pathlib.Path,
        default=ROOT / "data" / "sources.csv",
        help="The sources inventory (default: data/sources.csv).",
    )
    args = parser.parse_args(argv)

    raw_dir = args.sources.parent / "raw"
    with args.sources.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if in_corpus(row) or not args.only_corpus]

    if args.missing:
        return report_missing(rows, raw_dir)

    raw_dir.mkdir(parents=True, exist_ok=True)
    context = tls_context(args.insecure)
    downloaded = skipped = failed = no_link = 0

    for row in rows:
        local_path = (row.get("local_path") or "").strip()
        if not local_path.lower().endswith(".pdf"):
            continue
        doc_id = row["doc_id"]
        url = (row.get("source_url") or "").strip()
        dest = raw_dir / pathlib.PurePath(local_path).name

        if dest.exists() and is_valid_pdf(dest):
            print(f"[SKIP] {doc_id}: valid PDF already at {dest}", flush=True)
            skipped += 1
            continue
        if not is_direct_pdf_link(url):
            print(f"[NOLINK] {doc_id}: no direct PDF link; add {dest.name} by hand", flush=True)
            no_link += 1
            continue

        print(f"Downloading {doc_id} from {url} ...", flush=True)
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, context=context, timeout=TIMEOUT_SECONDS) as r:
                data = r.read()
            if not data.startswith(b"%PDF"):
                print(f"  [FAIL] {doc_id}: not a PDF (starts with {data[:20]!r})", flush=True)
                failed += 1
                continue
            # Write beside the target, then rename, so a cut-off download is never kept.
            partial = dest.with_suffix(".part")
            partial.write_bytes(data)
            os.replace(partial, dest)
            print(f"  saved {dest} ({len(data)} bytes)", flush=True)
            downloaded += 1
        except Exception as exc:  # network, TLS, HTTP errors
            print(f"  [FAIL] {doc_id}: {exc}", flush=True)
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) and not args.insecure:
                print("         (bad certificate: download by hand, or --insecure)", flush=True)
            failed += 1

    print(
        f"\nDone. downloaded {downloaded}, skipped (already valid) {skipped}, failed {failed}"
        f", no direct PDF link {no_link}.",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
