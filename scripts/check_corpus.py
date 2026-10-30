import csv
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "data" / "sources.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row.get("use_in_corpus", "").strip().upper() != "Y":
            continue
        p = ROOT / row["local_path"]
        if not p.is_file():
            print(f"MISSING   {row['doc_id']}  {row['local_path']}")
            continue
        head = p.read_bytes()[:1024]
        if b"%PDF-" not in head:
            print(f"NOT-PDF   {row['doc_id']}  {head[:20]!r}")
            continue
        with pdfplumber.open(p) as pdf:
            chars = sum(len(pg.extract_text() or "") for pg in pdf.pages)
            print(
                f"OK        {row['doc_id']}  pages={len(pdf.pages)} chars={chars}"
                + ("  LOW-TEXT" if chars < 200 * len(pdf.pages) else "")
            )
        if p.suffix.lower() != ".pdf":
            print(f"RENAME    {row['doc_id']}  is a PDF but named {p.suffix}")
