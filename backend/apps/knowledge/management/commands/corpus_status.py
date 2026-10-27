"""Show what has been ingested: chunks per document, and the vectors in Qdrant.

    python manage.py corpus_status [--collection NAME]

Read-only. Use it after ``ingest_corpus`` to check that every document has chunks and that
PostgreSQL and Qdrant agree. Works when Qdrant is down or qdrant-client is not installed.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.knowledge.models import Chunk, Document


class Command(BaseCommand):
    help = "Print chunks per document and the Qdrant point count."

    def add_arguments(self, parser):
        parser.add_argument(
            "--collection",
            default="sahkar_saathi_chunks",
            help="Qdrant collection name (default: sahkar_saathi_chunks).",
        )

    def handle(self, *args, **options):
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
