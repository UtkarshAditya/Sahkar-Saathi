import sys
import pathlib
import pdfplumber

folder = sys.argv[1] if len(sys.argv) > 1 else "data/raw"

for p in sorted(pathlib.Path(folder).glob("*.pdf")):
    try:
        with pdfplumber.open(p) as pdf:
            counts = [len(page.extract_text() or "") for page in pdf.pages]
        low = sum(1 for c in counts if c < 50)
        avg_chars = sum(counts) // max(len(counts), 1)
        print(f"{p.name}: {len(counts)} pages, {low} low-text pages, avg {avg_chars} chars", flush=True)
    except Exception as e:
        print(f"{p.name}: [ERROR reading PDF] {e}", flush=True)