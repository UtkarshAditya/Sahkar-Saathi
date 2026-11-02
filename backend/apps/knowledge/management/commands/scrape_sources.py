"""Fetch the official web pages in data/scrape_sources.yaml into the knowledge base.

    python manage.py scrape_sources [--only ID ...] [--dry-run] [--delay SECONDS] [--force]

For each source: fetch the page (services/scraper.py applies the allowlist, address,
size, content-type and robots.txt rules), clean it, drop lines that look like prompt
injection, and hash the text. Unchanged text is skipped. New or changed text creates or
updates the Document (source_kind "web") and replaces its chunks and Qdrant points through
the same helper as ingest_corpus. A failure on one source leaves that source's existing
chunks alone and does not stop the others.

Everything stays in memory; only PostgreSQL and Qdrant are written. Run it by hand or from
a scheduled job, never during a request.
"""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.knowledge.models import Document
from services.scraper import (
    Fetcher,
    ScrapeBlocked,
    ScrapeError,
    SourceListError,
    content_hash,
    load_sources,
    scrape_source,
)

from .ingest_corpus import chunk_pages, clean_page_text, ensure_collection, index_document_pages

COLLECTION = "sahkar_saathi_chunks"


def scrape_sources_path() -> Path:
    """SCRAPE_SOURCES, else backend/data/scrape_sources.yaml, else ../data (a dev checkout)."""
    if settings.SCRAPE_SOURCES:
        return Path(settings.SCRAPE_SOURCES)
    path = Path(settings.BASE_DIR) / "data" / "scrape_sources.yaml"
    parent = Path(settings.BASE_DIR).parent / "data" / "scrape_sources.yaml"
    return parent if not path.exists() and parent.exists() else path


@dataclass
class Row:
    id: str
    status: str  # new, updated, unchanged, blocked, error
    chars: int = 0
    chunks: int = 0
    dropped: int = 0
    reason: str = ""


class Indexer:
    """The embedding model and Qdrant client, loaded on first use: a run where nothing
    changed (or a dry run) never loads them."""

    def __init__(self, collection: str) -> None:
        self.collection = collection
        self._loaded = None

    def load(self):
        if self._loaded is None:
            try:
                from qdrant_client import QdrantClient
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ScrapeError(
                    f"the ML packages are missing ({exc}); install requirements-ml.txt"
                ) from exc
            model = SentenceTransformer(settings.EMBEDDING_MODEL)
            client = QdrantClient(url=settings.QDRANT_URL)
            ensure_collection(client, model, self.collection)
            self._loaded = (model, client)
        return self._loaded


class Command(BaseCommand):
    help = "Fetch the web pages in data/scrape_sources.yaml and index the new or changed ones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only", action="append", metavar="ID", help="Only this source id (repeatable)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Fetch and clean, print stats, write nothing."
        )
        parser.add_argument(
            "--delay",
            type=float,
            help="Seconds between requests (default: SCRAPE_DELAY_SECONDS, 2).",
        )
        parser.add_argument(
            "--force", action="store_true", help="Re-index even if the text is unchanged."
        )
        parser.add_argument("--sources", help="Source list (default: data/scrape_sources.yaml).")
        parser.add_argument("--collection", default=COLLECTION, help="Qdrant collection name.")

    def handle(self, *args, **options):
        path = Path(options["sources"]) if options["sources"] else scrape_sources_path()
        if not path.is_file():
            raise CommandError(f"Source list not found at {path}")
        try:
            sources = load_sources(path.read_text(encoding="utf-8"))
        except SourceListError as exc:
            raise CommandError(str(exc)) from exc

        # The allowlist is every host in the file, also with --only.
        allowed_hosts = {source.host for source in sources}
        if options["only"]:
            unknown = sorted(set(options["only"]) - {s.id for s in sources})
            if unknown:
                raise CommandError(f"Not in {path.name}: {', '.join(unknown)}")
            sources = [s for s in sources if s.id in options["only"]]
        if not sources:
            self.stdout.write(self.style.WARNING(f"No sources in {path}."))
            return

        delay = options["delay"] if options["delay"] is not None else settings.SCRAPE_DELAY_SECONDS
        dry_run = options["dry_run"]
        self.stdout.write(
            f"{len(sources)} source(s) from {path}, {delay:g} s between requests"
            + (" (dry run: nothing is written)" if dry_run else "")
        )
        fetcher = self.make_fetcher(allowed_hosts, delay)
        indexer = Indexer(options["collection"])
        rows: list[Row] = []
        try:
            for source in sources:
                rows.append(self.process(source, fetcher, indexer, dry_run, options["force"]))
        finally:
            fetcher.close()

        self.print_table(rows)
        failed = [r for r in rows if r.status in ("blocked", "error")]
        if failed:
            raise CommandError(
                f"{len(failed)} of {len(rows)} source(s) failed (see the table). Their "
                "existing chunks, if any, were kept."
            )

    def make_fetcher(self, allowed_hosts: set[str], delay: float) -> Fetcher:
        """A Fetcher for the allowlist. Tests replace this to inject a mocked client."""
        return Fetcher(allowed_hosts, delay=delay)

    def process(self, source, fetcher, indexer, dry_run: bool, force: bool) -> Row:
        try:
            page = scrape_source(source, fetcher)
        except ScrapeBlocked as exc:
            return Row(source.id, "blocked", reason=str(exc))
        except Exception as exc:  # ScrapeError, httpx errors, anything unexpected
            return Row(source.id, "error", reason=_reason(exc))

        text = clean_page_text(page.text)
        row = Row(source.id, "", chars=len(text), dropped=page.injection_dropped)
        if page.final_url != source.url:
            row.reason = f"redirected to {page.final_url}"
        pages = [(None, text)] if text else []
        row.chunks = len(chunk_pages(pages))
        if not row.chunks:
            row.status, row.reason = "error", "no usable text on the page (selector?)"
            return row

        digest = content_hash(text)
        document = Document.objects.filter(pk=source.id).first()
        if document is not None and document.content_hash == digest and not force:
            row.status = "unchanged"
            return row
        row.status = "new" if document is None else "updated"
        if dry_run:
            row.reason = _join(row.reason, "dry run, nothing written")
            return row

        try:
            model, client = indexer.load()
            with transaction.atomic():
                document = _apply(document, source, digest)
                written = index_document_pages(
                    document, pages, model, client, collection_name=indexer.collection
                )
                if written == 0:  # chunk_pages said otherwise; never keep a hash for nothing
                    raise ScrapeError("no chunks were written")
        except Exception as exc:
            # The transaction rolled back: the Document and its old chunks are as they were.
            return Row(source.id, "error", row.chars, row.chunks, row.dropped, _reason(exc))
        row.chunks = written
        return row

    def print_table(self, rows: list[Row]) -> None:
        write = self.stdout.write
        write("")
        write(f"{'id':<34} {'status':<9} {'chars':>7} {'chunks':>6} {'injection':>9}  reason")
        for r in rows:
            line = f"{r.id:<34} {r.status:<9} {r.chars:>7} {r.chunks:>6} {r.dropped:>9}  {r.reason}"
            if r.status in ("blocked", "error"):
                write(self.style.WARNING(line))
            else:
                write(line)
        dropped = sum(r.dropped for r in rows)
        if dropped:
            write(
                self.style.WARNING(
                    f"\n{dropped} line(s) that looked like prompt injection were dropped "
                    "before chunking. Read those pages by hand."
                )
            )


def _apply(document: Document | None, source, digest: str) -> Document:
    """Create or update the Document for a scraped page (saved, inside the caller's
    transaction). fetched_at is set before indexing, so the Qdrant payloads carry it."""
    now = timezone.now()
    if document is None:
        document = Document(id=source.id)
    document.title = source.title
    document.publisher = source.publisher
    document.doc_type = source.doc_type
    document.state = source.state
    document.language = source.language
    document.source_url = source.url
    document.version = f"Fetched {now:%Y-%m-%d}"
    document.status = Document.Status.ACTIVE
    document.is_sample = False
    document.source_kind = Document.SourceKind.WEB
    document.fetched_at = now
    document.content_hash = digest
    document.full_clean(exclude=["id"])
    document.save()
    return document


def _reason(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    if isinstance(exc, ScrapeBlocked | ScrapeError):
        return text
    return f"{exc.__class__.__name__}: {text}"


def _join(*parts: str) -> str:
    return "; ".join(p for p in parts if p)
