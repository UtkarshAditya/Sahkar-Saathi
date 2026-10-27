"""Show what has been ingested, or (with --files) what the corpus files look like.

    python manage.py corpus_status [--collection NAME]
    python manage.py corpus_status --files

Read-only. Without options: chunks per document and the vectors in Qdrant. Use it after
``ingest_corpus`` to check that every document has chunks and that PostgreSQL and Qdrant
agree. Works when Qdrant is down or qdrant-client is not installed.

With --files: for every ``use_in_corpus=Y`` row of sources.csv, whether its PDF is where
ingest_corpus will look (the name is matched exactly, as in the Linux container, even on
Windows), whether it starts with the PDF signature, and, when pdfplumber is installed, its
page count and amount of text. Files with very little text per page are probably scanned
images, which ingest_corpus cannot read. This needs neither the database nor Qdrant, so it
can be run before the first ingest.
"""

import csv
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.knowledge.models import Chunk, Document

LOW_TEXT_CHARS_PER_PAGE = 100  # below this average, the PDF is probably a scan


def sources_csv_path() -> Path:
    """The sources.csv ingest_corpus would read: SOURCES_CSV, else backend/data, else ../data."""
    env = os.environ.get("SOURCES_CSV")
    if env:
        return Path(env)
    path = Path(settings.BASE_DIR) / "data" / "sources.csv"
    parent = Path(settings.BASE_DIR).parent / "data" / "sources.csv"
    return parent if not path.exists() and parent.exists() else path


def find_file(local_path: str) -> tuple[Path | None, str]:
    """Where ingest_corpus would find ``local_path``, matching the file name exactly.

    Returns (path, "ok") for an exact match, (None, "case differs: NAME") when only the case
    of the name differs, and (None, "missing") otherwise. ingest_corpus tries backend/ first,
    then the repository root.
    """
    if not local_path:
        return None, "no local_path"
    near_miss = ""
    for base in (Path(settings.BASE_DIR), Path(settings.BASE_DIR).parent):
        candidate = base / local_path
        folder = candidate.parent
        names = os.listdir(folder) if folder.is_dir() else []
        if candidate.name in names:
            return candidate, "ok"
        near_miss = near_miss or next((n for n in names if n.lower() == candidate.name.lower()), "")
    return None, f"case differs: {near_miss}" if near_miss else "missing"


def text_stats(path: Path):
    """(pages, characters) with pdfplumber, None if it is not installed, or an error string."""
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(path) as pdf:
            pages = [len(page.extract_text() or "") for page in pdf.pages]
    except Exception as exc:  # corrupt, encrypted or not a PDF
        return f"unreadable ({exc.__class__.__name__})"
    return len(pages), sum(pages)


class Command(BaseCommand):
    help = "Print chunks per document and the Qdrant point count, or check the corpus files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--collection",
            default="sahkar_saathi_chunks",
            help="Qdrant collection name (default: sahkar_saathi_chunks).",
        )
        parser.add_argument(
            "--files",
            action="store_true",
            help="Check the PDF of every use_in_corpus=Y row instead (no database or Qdrant).",
        )

    def handle(self, *args, **options):
        if options["files"]:
            return self.report_files()
        collection = options["collection"]
        documents = Document.objects.annotate(chunk_count=Count("chunks")).order_by("id")

        self.stdout.write(f"{'document':<46} {'state':<8} chunks")
        empty: list[str] = []
        for doc in documents:
            self.stdout.write(f"{doc.id:<46} {doc.state:<8} {doc.chunk_count}")
            if doc.chunk_count == 0:
                empty.append(doc.id)

        total = Chunk.objects.count()
        self.stdout.write(f"\nDocuments: {len(documents)}   Chunk rows: {total}")

        points = self._qdrant_points(collection)
        self.stdout.write(f"Qdrant collection '{collection}': {points}")
        if isinstance(points, int) and points != total:
            self.stdout.write(
                self.style.WARNING(
                    f"PostgreSQL has {total} chunk rows but Qdrant has {points} points. "
                    "Run ingest_corpus again."
                )
            )

        if empty:
            self.stdout.write(self.style.WARNING(f"\nDocuments with zero chunks ({len(empty)}):"))
            for doc_id in empty:
                self.stdout.write(f"  {doc_id}")
        else:
            self.stdout.write(self.style.SUCCESS("\nEvery document has chunks."))

    # --- --files ------------------------------------------------------------------------

    def report_files(self) -> None:
        csv_path = sources_csv_path()
        if not csv_path.is_file():
            raise CommandError(f"sources.csv not found at {csv_path}")
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [
                r for r in csv.DictReader(handle) if (r.get("use_in_corpus") or "").strip() == "Y"
            ]

        self.stdout.write(f"{csv_path}: {len(rows)} rows with use_in_corpus=Y\n")
        self.stdout.write(
            f"{'doc_id':<36} {'file':<8} {'%PDF':<5} {'pages':>6} {'chars':>9} "
            f"{'chars/pg':>8}  expected path / note"
        )
        present = missing = low_text = 0
        pdfplumber_missing = False
        for row in rows:
            local_path = (row.get("local_path") or "").strip()
            path, status = find_file(local_path)
            pages = chars = per_page = "-"
            note = local_path or "(no local_path)"
            is_pdf = "-"
            file_cell = "MISSING"

            if path is None:
                missing += 1
                if status.startswith("case differs"):
                    file_cell = "CASE"
                    note += f"   <- {status}"
                elif status == "no local_path":
                    note = "(no local_path in the CSV)"
                if local_path and not local_path.lower().endswith(".pdf"):
                    note += "   [not a .pdf path: ingest_corpus reads PDFs only]"
            else:
                present += 1
                file_cell = "present"
                with path.open("rb") as handle:
                    is_pdf = "yes" if handle.read(4) == b"%PDF" else "NO"
                if is_pdf == "NO":
                    note += "   <- not a PDF (starts with something else)"
                else:
                    stats = text_stats(path)
                    if stats is None:
                        pdfplumber_missing = True
                        pages = chars = per_page = "n/a"
                    elif isinstance(stats, str):
                        note += f"   <- {stats}"
                    else:
                        page_count, char_count = stats
                        average = char_count // max(page_count, 1)
                        pages, chars, per_page = page_count, char_count, average
                        if average < LOW_TEXT_CHARS_PER_PAGE:
                            low_text += 1
                            note += "   <- LOW TEXT: probably scanned, ingest will find little"
            line = (
                f"{row['doc_id']:<36} {file_cell:<8} {is_pdf:<5} {pages!s:>6} {chars!s:>9} "
                f"{per_page!s:>8}  {note}"
            )
            self.stdout.write(line)

        if pdfplumber_missing:
            self.stdout.write(
                self.style.WARNING(
                    "\npdfplumber not installed: page and character counts are not shown. "
                    "Install requirements-ml.txt (or run this inside the web container)."
                )
            )
        self.stdout.write(
            f"\nY documents: {len(rows)}   files present: {present}   "
            f"files missing: {missing}   low-text files: {low_text}"
        )

    # --- Qdrant -------------------------------------------------------------------------

    def _qdrant_points(self, collection: str) -> int | str:
        """The point count, or a sentence saying why it is not available."""
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            return "qdrant-client is not installed"
        try:
            client = QdrantClient(url=settings.QDRANT_URL)
            names = [c.name for c in client.get_collections().collections]
            if collection not in names:
                return "collection does not exist yet (run ingest_corpus)"
            return int(client.count(collection_name=collection, exact=True).count)
        except Exception as exc:  # connection refused, timeout, bad response
            return f"Qdrant not reachable at {settings.QDRANT_URL} ({exc.__class__.__name__})"
