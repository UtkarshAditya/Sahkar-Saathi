import csv
import uuid
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.knowledge.models import Document, Chunk
import pdfplumber
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models


class Command(BaseCommand):
    help = "Ingest verified corpus PDFs: chunk text, generate embeddings, seed Qdrant, and save Chunks in PostgreSQL."

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
            self.stdout.write(f"Creating Qdrant collection '{collection_name}' with size {vector_size}...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

        csv_path = Path(settings.BASE_DIR).parent / "data" / "sources.csv"
        if not csv_path.exists():
            self.stdout.write(self.style.ERROR("data/sources.csv not found!"))
            return

        self.stdout.write("Reading sources.csv and processing corpus...")

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
                    self.stdout.write(self.style.WARNING(f"PDF file not found at {pdf_file}"))
                    continue

                self.stdout.write(f"Processing PDF for document: {doc_id}...")

                # Clear existing chunks for this doc to prevent duplication on re-runs
                Chunk.objects.filter(document=document).delete()

                chunk_records = []
                qdrant_points = []

                with pdfplumber.open(pdf_file) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if not text:
                            continue

                        # Chunking text into ~500 character blocks
                        paragraphs = text.split("\n\n")
                        current_chunk = ""

                        for para in paragraphs:
                            if len(current_chunk) + len(para) < 500:
                                current_chunk += "\n\n" + para if current_chunk else para
                            else:
                                if current_chunk.strip():
                                    chunk_text = current_chunk.strip()
                                    vector_id = str(uuid.uuid4())
                                    embedding = model.encode(chunk_text).tolist()

                                    chunk_records.append(
                                        Chunk(
                                            document=document,
                                            text=chunk_text,
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
                                            payload={
                                                "doc_id": document.id,
                                                "document_title": document.title,
                                                "publisher": document.publisher,
                                                "source_url": document.source_url,
                                                "published_date": str(document.published_date) if document.published_date else None,
                                                "state": document.state,
                                                "language": document.language,
                                                "page": page_num,
                                                "text": chunk_text,
                                            },
                                        )
                                    )
                                current_chunk = para

                        if current_chunk.strip():
                            chunk_text = current_chunk.strip()
                            vector_id = str(uuid.uuid4())
                            embedding = model.encode(chunk_text).tolist()

                            chunk_records.append(
                                Chunk(
                                    document=document,
                                    text=chunk_text,
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
                                    payload={
                                        "doc_id": document.id,
                                        "state": document.state,
                                        "language": document.language,
                                        "page": page_num,
                                        "text": chunk_text,
                                    },
                                )
                            )

                # Bulk insert records into PostgreSQL
                if chunk_records:
                    Chunk.objects.bulk_create(chunk_records)
                    self.stdout.write(f"Saved {len(chunk_records)} chunks to PostgreSQL for {doc_id}.")

                # Upsert vectors into Qdrant
                if qdrant_points:
                    client.upsert(
                        collection_name=collection_name,
                        points=qdrant_points,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"Upserted {len(qdrant_points)} vectors to Qdrant for {doc_id}.")
                    )

        self.stdout.write(self.style.SUCCESS("Corpus ingestion and vector seeding completed successfully!"))