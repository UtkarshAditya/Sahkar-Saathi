import csv
import os
import uuid
from pathlib import Path

import pdfplumber
from django.conf import settings
from django.core.management.base import BaseCommand
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer

from apps.knowledge.models import Chunk, Document


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks by character length with overlap (~500 chars, ~50 chars overlap)."""
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


def build_chunk_payload(
    document: Document,
    page: int | None,
    text: str,
) -> dict:
    """Build standardized chunk payload dictionary for Qdrant storage."""
    if not text.startswith("passage: "):
        text = f"passage: {text}"
    return {
        "doc_id": document.id,
        "document_title": document.title,
        "publisher": document.publisher,
        "source_url": document.source_url,
        "published_date": str(document.published_date) if document.published_date else None,
        "state": document.state,
        "language": document.language,
        "page": page,
        "text": text,
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
        collection_name = options["collection"]
        self.stdout.write("Initializing embedding model...")
        model = SentenceTransformer(settings.EMBEDDING_MODEL)

        self.stdout.write("Connecting to Qdrant...")
        qdrant_url = getattr(settings, "QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url)

        # Ensure Qdrant collection exists
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
            self.stdout.write(self.style.ERROR(f"sources.csv not found at {csv_path}!"))
            return

        self.stdout.write(f"Reading {csv_path} and processing corpus...")

        with open(csv_path, encoding="utf-8") as f:
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
                    continue

                project_root = Path(settings.BASE_DIR).parent
                pdf_file = project_root / local_path
                if not pdf_file.exists():
                    pdf_file = settings.BASE_DIR / local_path
                if not pdf_file.exists():
                    self.stdout.write(self.style.WARNING(f"PDF file not found at {pdf_file}"))
                    continue

                self.stdout.write(f"Processing PDF for document: {doc_id}...")

                # Clear existing chunks for this doc to prevent duplication on re-runs
                Chunk.objects.filter(document=document).delete()

                chunk_records = []
                qdrant_points = []

                with pdfplumber.open(pdf_file) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        raw_text = page.extract_text()
                        if not raw_text:
                            continue

                        # Chunking text into ~500 character blocks with ~50 chars overlap
                        chunks = chunk_text(raw_text, chunk_size=500, overlap=50)

                        for chunk_str in chunks:
                            passage_text = f"passage: {chunk_str}"
                            vector_id = str(uuid.uuid4())
                            embedding = model.encode(passage_text).tolist()

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
                                        text=passage_text,
                                    ),
                                )
                            )

                # Clear existing points for this document from Qdrant before upserting
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

                # Bulk insert records into PostgreSQL
                if chunk_records:
                    Chunk.objects.bulk_create(chunk_records)
                    self.stdout.write(
                        f"Saved {len(chunk_records)} chunks to PostgreSQL for {doc_id}."
                    )

                # Upsert vectors into Qdrant
                if qdrant_points:
                    client.upsert(
                        collection_name=collection_name,
                        points=qdrant_points,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Upserted {len(qdrant_points)} vectors to Qdrant for {doc_id}."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS("Corpus ingestion and vector seeding completed successfully!")
        )
