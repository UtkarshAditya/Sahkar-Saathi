import csv
import logging
import os
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Chunk, Document

# Suppress verbose pdfminer logs/warnings during PDF extraction
logging.getLogger("pdfminer").setLevel(logging.ERROR)

PASSAGE_PREFIX = "passage: "

ABBREVIATIONS = {
    "e.g.",
    "i.e.",
    "viz.",
    "etc.",
    "no.",
    "nos.",
    "g.s.r.",
    "s.o.",
    "s.",
    "sec.",
    "r.",
    "u/s",
    "w.e.f.",
    "pvt.",
    "ltd.",
    "govt.",
    "rs.",
    "vs.",
    "para.",
    "dr.",
    "mr.",
    "mrs.",
    "g.o.",
}

CRCS_BOILERPLATE_PATTERNS = [
    r"^Go to Main Content Sitemap.*$",
    r"^Government of India\s*$",
    r"^Registration of New MSCS\s*$",
    r"^Ministry of Cooperation(?:\s+CR Login.*)?$",
    r"^Central Registrar of Cooperative(?:\s+Societies Login)?\s*$",
    r"^Societies Login\s*$",
    r"^Home\s*/\s*(?:About Cea|FAQs|Cooperative Ombudsman)\s*$",
    r"^Last updated:.*$",
    r"^Home\s+State Registrars\s+List of MSCS.*$",
    r"^Terms & Conditions\s+Copyright Policy.*$",
    r"^© Content Owned by Ministry of Cooperation.*$",
]

TN_RCS_FOOTER_PATTERNS = [
    r"^OFFICE OF THE REGISTRAR OF COOPERATIVE SOCIETIES.*$",
    r"^NVN Natarajan Maligai.*$",
    r"^No\.170, Periyar E\.V\.R\. High Road.*$",
    r"^E-Rcs Image Gallery.*$",
    r"^Kilpauk Chennai - 600 010.*$",
    r"^Tamilnadu\..*$",
    r"^Phone No\.:.*$",
    r"^Fax No\.:.*$",
    r"^Paniyaalar Naal VILUTHUGAL.*$",
    r"^Email id:\s*rcs\.tn@nic\.in.*$",
    r"^VERGAL Contact Us.*$",
    r"^Contact Us\s*$",
    r"^Copyright © \d{4}, All Right Reserved REGISTRAR OF COOPERATIVE SOCIETIES.*$",
    r"^designed by Trophy systems.*$",
]

ALL_BOILERPLATE_RE = re.compile(
    "|".join(f"(?:{p})" for p in CRCS_BOILERPLATE_PATTERNS + TN_RCS_FOOTER_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)


def clean_page_text(text: str) -> str:
    """Clean extracted page text by stripping glyphs and specific header/footer boilerplate.

    Never strips 'maintenance' or general domain terms.
    """
    if not text:
        return ""
    # 1. Strip (cid:NNN) artifacts
    text = re.sub(r"\(cid:\d+\)", "", text)
    # 2. Strip FontAwesome / private use glyphs
    text = re.sub(r"[\uf000-\uf8ff]", "", text)
    # 3. Strip CRCS navigation/footer and TN-RCS-ADMIN-DEPT footer
    text = ALL_BOILERPLATE_RE.sub("", text)
    # 4. Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def is_mostly_glyph_garbage(text: str) -> bool:
    """Detect if a page text is predominantly unreadable (cid:NNN) glyph codes."""
    if not text or not text.strip():
        return False
    cids = re.findall(r"\(cid:\d+\)", text)
    if not cids:
        return False
    cid_chars = sum(len(c) for c in cids)
    return len(cids) > 20 or (cid_chars / max(1, len(text)) > 0.25)


def extract_page_pypdf(pdf_file: Path, page_index: int) -> str:
    """Fallback pypdf extraction for pages where pdfminer produced glyph garbage."""
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_file))
        if 0 <= page_index < len(reader.pages):
            return reader.pages[page_index].extract_text() or ""
    except Exception:
        pass
    return ""


def is_heading(line: str) -> bool:
    """Detect numbered section headings like '32. General meetings' or 'CHAPTER III'."""
    line = line.strip()
    return bool(
        re.match(r"^(?:\d{1,4}(?:\.\d+)*\.?|\([a-z0-9]+\))\s+[A-Z]", line)
        or re.match(r"^(?:CHAPTER|SECTION|RULE|PART|CLAUSE)\s+[A-Z0-9IVX]+", line, re.I)
    )


def split_sentences(text: str) -> list[tuple[str, bool]]:
    """Split text into sentence units with heading flags, respecting legal abbreviations."""
    lines = text.splitlines()
    units: list[tuple[str, bool]] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_heading(line):
            units.append((line, True))
            continue

        # Split on sentence end punctuation (. ! ?) followed by space and capital letter/quote/digit
        tokens = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\(\[\"\'])", line)
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            if (
                units
                and not units[-1][1]
                and any(units[-1][0].lower().endswith(abbr) for abbr in ABBREVIATIONS)
            ):
                prev_text, _ = units.pop()
                units.append((prev_text + " " + t, False))
            else:
                units.append((t, False))

    return units


def split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """Split a sentence exceeding max_chars on word boundaries, never splitting mid-word."""
    words = sentence.split()
    parts: list[str] = []
    curr: list[str] = []
    curr_len = 0
    for w in words:
        if curr and (curr_len + len(w) + 1 > max_chars):
            parts.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += (len(w) + 1) if curr_len > 0 else len(w)
    if curr:
        parts.append(" ".join(curr))
    return parts


def chunk_text(
    text: str,
    max_chars: int = 900,
    min_chars: int = 80,
    tail_merge_chars: int = 150,
) -> list[str]:
    """Split text into section/sentence-aware chunks with sentence overlap.

    - Cleans glyph artifacts and specific header/footer boilerplate.
    - Never splits mid-word.
    - Splits on sentences and numbered section headings.
    - Carries over one sentence overlap between chunks.
    - Merges trailing fragment into previous chunk if <= tail_merge_chars.
    - Discards chunks < min_chars.
    """
    cleaned = clean_page_text(text)
    if not cleaned:
        return []

    units = split_sentences(cleaned)
    if not units:
        return []

    # Handle any single sentences that exceed max_chars
    expanded_units: list[tuple[str, bool]] = []
    for text_val, heading_flag in units:
        if len(text_val) > max_chars:
            for sub_text in split_long_sentence(text_val, max_chars):
                expanded_units.append((sub_text, heading_flag))
        else:
            expanded_units.append((text_val, heading_flag))

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_len = 0

    for sent, heading in expanded_units:
        sent_len = len(sent)

        # Break on section headings if current chunk already has sufficient content
        if heading and current_len >= min_chars:
            chunk_str = " ".join(current_sentences).strip()
            chunks.append(chunk_str)
            current_sentences = [sent]
            current_len = sent_len
            continue

        # If adding sentence exceeds max_chars, finalize chunk
        if current_sentences and (current_len + sent_len + 1 > max_chars):
            chunk_str = " ".join(current_sentences).strip()
            chunks.append(chunk_str)

            # One-sentence overlap: carry over last sentence if not excessively long
            overlap_sent = current_sentences[-1]
            if len(overlap_sent) < max_chars // 2:
                current_sentences = [overlap_sent, sent]
                current_len = len(overlap_sent) + 1 + sent_len
            else:
                current_sentences = [sent]
                current_len = sent_len
        else:
            current_sentences.append(sent)
            current_len += (sent_len + 1) if current_len > 0 else sent_len

    if current_sentences:
        last_chunk = " ".join(current_sentences).strip()
        # Merge trailing fragment into previous chunk if <= tail_merge_chars
        if chunks and len(last_chunk) <= tail_merge_chars:
            chunks[-1] = chunks[-1] + " " + last_chunk
        elif len(last_chunk) >= min_chars:
            chunks.append(last_chunk)

    return [c for c in chunks if len(c) >= min_chars]


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
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete Qdrant collection and truncate Chunk rows in DB before ingesting.",
        )

    def handle(self, *args, **options):
        # Ensure pdfminer logging level is suppressed
        logging.getLogger("pdfminer").setLevel(logging.ERROR)

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

        if options.get("reset"):
            self.stdout.write(
                self.style.WARNING(
                    f"Reset flag provided: deleting Qdrant collection '{collection_name}' "
                    "and deleting all Chunk rows from PostgreSQL..."
                )
            )
            if exists:
                client.delete_collection(collection_name=collection_name)
                exists = False
            deleted_count, _ = Chunk.objects.all().delete()
            self.stdout.write(f"Deleted {deleted_count} Chunk rows from PostgreSQL.")

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

        max_chars = getattr(settings, "CHUNK_MAX_CHARS", 900)
        min_chars = getattr(settings, "CHUNK_MIN_CHARS", 80)
        tail_merge_chars = getattr(settings, "CHUNK_TAIL_MERGE_CHARS", 150)

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
                    # Validate magic-byte header so non-PDF / HTML pages do not crash parser
                    with open(pdf_file, "rb") as header_file:
                        file_header = header_file.read(5)
                    if not file_header.startswith(b"%PDF-"):
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping non-PDF file for {doc_id} (header: {file_header!r})"
                            )
                        )
                        problems.append(
                            (doc_id, f"Not a valid PDF (invalid header {file_header!r})")
                        )
                        continue

                    pages_and_chunks: list[tuple[int, str]] = []
                    with pdfplumber.open(pdf_file) as pdf:
                        for page_num, page in enumerate(pdf.pages, start=1):
                            raw_text = page.extract_text() or ""
                            if is_mostly_glyph_garbage(raw_text):
                                pypdf_text = extract_page_pypdf(pdf_file, page_num - 1)
                                if pypdf_text and not is_mostly_glyph_garbage(pypdf_text):
                                    raw_text = pypdf_text
                                else:
                                    msg = f"Page {page_num} skipped (mostly (cid:) glyph garbage)"
                                    problems.append((doc_id, msg))
                                    continue

                            for chunk_str in chunk_text(
                                raw_text,
                                max_chars=max_chars,
                                min_chars=min_chars,
                                tail_merge_chars=tail_merge_chars,
                            ):
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
                        emb_raw = model.encode(embedding_input(chunk_str))
                        embedding = (
                            emb_raw.tolist() if hasattr(emb_raw, "tolist") else list(emb_raw)
                        )

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
