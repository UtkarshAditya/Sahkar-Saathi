import csv
import pathlib
import urllib.request
import ssl

# Define local data directory
raw_dir = pathlib.Path("data/raw")
raw_dir.mkdir(parents=True, exist_ok=True)

# Custom headers to bypass government site user-agent blocks
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/pdf,*/*'
}

# Context to ignore self-signed SSL errors if any gov site has certificate issues
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

with open("data/sources.csv", "r", encoding="utf-8") as f:
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
                        print(f"[SKIP] {row['doc_id']}: Valid PDF already exists at {dest_file}", flush=True)
                        continue

            # Only attempt if there is a direct PDF link
            if not url or not (url.lower().endswith(".pdf") or ".pdf" in url.lower().split("?")[0]):
                continue

            print(f"Downloading {row['doc_id']} from {url}...", flush=True)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                    data = response.read()
                    if not data.startswith(b"%PDF"):
                        print(f"  [ERROR] {row['doc_id']}: URL returned non-PDF content (starts with {data[:20]!r}). Skipping.", flush=True)
                        continue
                    with open(dest_file, 'wb') as out_file:
                        out_file.write(data)
                print(f"  --> Saved to {dest_file} ({len(data)} bytes)", flush=True)
            except Exception as e:
                print(f"  [ERROR] Could not download {row['doc_id']}: {e}", flush=True)

print("\nDone checking and downloading files!", flush=True)