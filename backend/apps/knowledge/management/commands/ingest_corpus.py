import csv
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Chunk, Document

PASSAGE_PREFIX = "passage: "


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_len = len(text)
    step = max(1, chunk_size - overlap)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start += step
    return chunks


def embedding_input(text: str) -> str:
    return f"{PASSAGE_PREFIX}{text}"


def build_chunk_payload(
    document: Document,
    page: int | None,
    text: str,
) -> dict:
    return {
        "doc_id": document.id,
        "document_title": document.title,
        "publisher": document.publisher,
        "source_url": document.source_url,
        "published_date": str(document.published_date) if document.published_date else None,
        "state": document.state,
        "language": document.language,
        "page": page,
        "text": text.removeprefix(PASSAGE_PREFIX),
    }


class Command(BaseCommand):
    help = (
        "Ingest verified corpus PDFs: chunk text, generate embeddings, "
        "seed Qdrant, and save Chunks in PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--collection",
            default="sahkar_saathi_chunks",
            help="Qdrant collection name",
        )

    def handle(self, *args, **options):
        try:
            import pdfplumber
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qdrant_models
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise CommandError(
                f"ingest_corpus needs the ML packages ({exc}). Install requirements-ml.txt, "
                "or in Docker build with INSTALL_ML=true."
            ) from exc

        collection_name = options["collection"]
        self.stdout.write("Initializing embedding model...")
        model = SentenceTransformer(settings.EMBEDDING_MODEL)

        self.stdout.write("Connecting to Qdrant...")
        qdrant_url = getattr(settings, "QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url)

        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        vector_size = model.get_embedding_dimension()

        if not exists:
            self.stdout.write(
                f"Creating Qdrant collection '{collection_name}' with size {vector_size}..."
            )
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

        sources_csv_env = os.environ.get("SOURCES_CSV")
        if sources_csv_env:
            csv_path = Path(sources_csv_env)
        else:
            csv_path = settings.BASE_DIR / "data" / "sources.csv"
            parent_csv = Path(settings.BASE_DIR).parent / "data" / "sources.csv"
            if not csv_path.exists() and parent_csv.exists():
                csv_path = parent_csv

        if not csv_path.exists():
            raise CommandError(f"sources.csv not found at {csv_path}!")

        self.stdout.write(f"Reading {csv_path} and processing corpus...")

        documents_processed = 0
        chunks_written = 0
        vectors_upserted = 0
        problems: list[tuple[str, str]] = []

        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("use_in_corpus", "").strip().upper() != "Y":
                    continue

                doc_id = row["doc_id"]
                local_path = row.get("local_path", "").strip()

                try:
                    document = Document.objects.get(id=doc_id)
                except Document.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Document {doc_id} not found in PostgreSQL. Run load_sources first."
                        )
                    )
                    problems.append((doc_id, "no Document row (run load_sources; row skipped?)"))
                    continue

                pdf_file = settings.BASE_DIR / local_path if local_path else None
                if pdf_file is None or not pdf_file.is_file():
                    pdf_file = Path(settings.BASE_DIR).parent / local_path if local_path else None
                if pdf_file is None or not pdf_file.is_file():
                    self.stdout.write(
                        self.style.WARNING(f"PDF file not found for {doc_id}: {local_path!r}")
                    )
                    problems.append((doc_id, f"PDF not found ({local_path or 'no local_path'})"))
                    continue

                self.stdout.write(f"Processing PDF for document: {doc_id}...")

                try:
                    # Explicit magic-byte header validation to prevent non-PDF/HTML error pages from crashing parser
                    with open(pdf_file, "rb") as header_file:
                        file_header = header_file.read(5)
                    if not file_header.startswith(b"%PDF-"):
                        self.stdout.write(
                            self.style.WARNING(f"Skipping non-PDF file for {doc_id} (header: {file_header!r})")
                        )
                        problems.append((doc_id, f"Not a valid PDF (invalid header {file_header!r})"))
                        continue

                    pages_and_chunks: list[tuple[int, str]] = []
                    with pdfplumber.open(pdf_file) as pdf:
                        for page_num, page in enumerate(pdf.pages, start=1):
                            raw_text = page.extract_text()
                            if not raw_text:
                                continue
                            for chunk_str in chunk_text(raw_text, chunk_size=500, overlap=50):
                                pages_and_chunks.append((page_num, chunk_str))

                    documents_processed += 1
                    if not pages_and_chunks:
                        problems.append((doc_id, "PDF yielded zero chunks (scanned, no text?)"))
                        continue

                    Chunk.objects.filter(document=document).delete()

                    chunk_records = []
                    qdrant_points = []

                    for page_num, chunk_str in pages_and_chunks:
                        vector_id = str(uuid.uuid4())
                        embedding = model.encode(embedding_input(chunk_str)).tolist()

                        chunk_records.append(
                            Chunk(
                                document=document,
                                text=chunk_str,
                                page=page_num,
                                state=document.state,
                                language=document.language,
                                vector_id=vector_id,
                            )
                        )
                        qdrant_points.append(
                            qdrant_models.PointStruct(
                                id=vector_id,
                                vector=embedding,
                                payload=build_chunk_payload(
                                    document=document,
                                    page=page_num,
                                    text=chunk_str,
                                ),
                            )
                        )

                    client.delete(
                        collection_name=collection_name,
                        points_selector=qdrant_models.FilterSelector(
                            filter=qdrant_models.Filter(
                                must=[
                                    qdrant_models.FieldCondition(
                                        key="doc_id",
                                        match=qdrant_models.MatchValue(value=doc_id),
                                    )
                                ]
                            )
                        ),
                    )

                    if chunk_records:
                        Chunk.objects.bulk_create(chunk_records)
                        chunks_written += len(chunk_records)
                        self.stdout.write(
                            f"Saved {len(chunk_records)} chunks to PostgreSQL for {doc_id}."
                        )

                    if qdrant_points:
                        client.upsert(
                            collection_name=collection_name,
                            points=qdrant_points,
                        )
                        vectors_upserted += len(qdrant_points)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Upserted {len(qdrant_points)} vectors to Qdrant for {doc_id}."
                            )
                        )

                except Exception as exc:
                    self.stdout.write(
                        self.style.WARNING(f"Skipping corrupt or invalid PDF for {doc_id}: {exc}")
                    )
                    problems.append((doc_id, f"PDF could not be read ({exc.__class__.__name__})"))
                    continue

        self.stdout.write(
            f"\nIngest summary: documents processed {documents_processed}, "
            f"chunks written {chunks_written}, vectors upserted {vectors_upserted}."
        )
        if problems:
            self.stdout.write(
                self.style.WARNING(f"{len(problems)} use_in_corpus=Y document(s) need attention:")
            )
            for doc_id, why in problems:
                self.stdout.write(self.style.WARNING(f"  {doc_id}: {why}"))
        if chunks_written == 0:
            raise CommandError(
                "No chunks were written. Check that the PDFs are in data/raw/ and that "
                "load_sources has loaded their Document rows."
            )
        self.stdout.write(
            self.style.SUCCESS("Corpus ingestion and vector seeding completed.")
            if not problems
            else self.style.WARNING("Corpus ingestion completed, with the problems listed above.")
        )