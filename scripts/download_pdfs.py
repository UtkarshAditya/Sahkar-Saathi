<<<<<<< HEAD
import csv
import pathlib
import ssl
import urllib.request

# Define local data directory
raw_dir = pathlib.Path("data/raw")
raw_dir.mkdir(parents=True, exist_ok=True)

# Custom headers to bypass government site user-agent blocks
headers = {
=======
#!/usr/bin/env python3
"""Download the source PDFs listed in data/sources.csv into data/raw/ (which git ignores).

    python scripts/download_pdfs.py             # TLS certificates are verified
    python scripts/download_pdfs.py --insecure  # skips verification: see the warning below

Only rows whose local_path ends in .pdf and whose source_url is a direct PDF link are
tried. Files that already start with the PDF signature are kept, so it is safe to re-run.
The PDFs the script cannot fetch (pages, not files) come from the team Drive instead.
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
>>>>>>> 1fa451cba04f0e8dd774cf42daf1bcab8a74ef4f
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
}

<<<<<<< HEAD
# Context to ignore self-signed SSL errors if any gov site has certificate issues
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

with open("data/sources.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Download only files that are active and have a PDF local path
        if row.get("local_path", "").endswith(".pdf"):
            url = row.get("source_url", "").strip()
            dest_path = pathlib.Path(row["local_path"])
            dest_file = raw_dir / dest_path.name

            # Check if already present and valid
            if dest_file.exists():
                with open(dest_file, "rb") as check_fp:
                    if check_fp.read(4) == b"%PDF":
                        print(
                            f"[SKIP] {row['doc_id']}: Valid PDF already exists at {dest_file}",
                            flush=True,
                        )
                        continue

            # Only attempt if there is a direct PDF link
            if not url or not (
                url.lower().endswith(".pdf") or ".pdf" in url.lower().split("?")[0]
            ):
                continue

            print(f"Downloading {row['doc_id']} from {url}...", flush=True)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                    data = response.read()
                    if not data.startswith(b"%PDF"):
                        print(
                            f"  [ERROR] {row['doc_id']}: URL returned non-PDF content "
                            f"(starts with {data[:20]!r}). Skipping.",
                            flush=True,
                        )
                        continue
                    with open(dest_file, "wb") as out_file:
                        out_file.write(data)
                print(f"  --> Saved to {dest_file} ({len(data)} bytes)", flush=True)
            except Exception as e:
                print(f"  [ERROR] Could not download {row['doc_id']}: {e}", flush=True)

print("\nDone checking and downloading files!", flush=True)
=======

def is_valid_pdf(path: pathlib.Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(4) == b"%PDF"


def is_direct_pdf_link(url: str) -> bool:
    return bool(url) and ".pdf" in url.lower().split("?")[0]


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the source PDFs into data/raw/.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Do not verify TLS certificates (unsafe; for sites with a broken certificate).",
    )
    parser.add_argument(
        "--sources",
        type=pathlib.Path,
        default=ROOT / "data" / "sources.csv",
        help="The sources inventory (default: data/sources.csv).",
    )
    args = parser.parse_args(argv)

    raw_dir = args.sources.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    context = tls_context(args.insecure)
    downloaded = skipped = failed = no_link = 0

    with args.sources.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
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
>>>>>>> 1fa451cba04f0e8dd774cf42daf1bcab8a74ef4f
