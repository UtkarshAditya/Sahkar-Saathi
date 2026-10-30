import csv
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Chunk, Document

# The ML packages (pdfplumber, pypdf, qdrant-client, sentence-transformers) are imported
# inside handle() or inside the functions that need them, so this module, and its helpers
# below, import without them (CI has none).

# multilingual-e5 expects this prefix on passages. It belongs on the string that is
# embedded only; the stored text (Chunk rows and Qdrant payloads) stays clean.
PASSAGE_PREFIX = "passage: "
PDF_MAGIC = b"%PDF-"

# Defaults for chunk_text; handle() passes the CHUNK_* settings instead.
DEFAULT_MAX_CHARS = 900
DEFAULT_MIN_CHARS = 80
DEFAULT_TAIL_MERGE_CHARS = 150

# A page is read again with pypdf when at least this share of its non-space characters is
# font garbage ("(cid:12)" tokens and private-use glyphs) in what pdfplumber extracted.
GLYPH_GARBAGE_SHARE = 0.5

_CID_TOKEN = re.compile(r"\(cid:\d+\)")
# Private-use code points (icon fonts such as Font Awesome) and the replacement character.
_PRIVATE_USE = re.compile("[-�]")

# Whole lines of web-page and footer boilerplate that PDFs printed from the CRCS and Tamil
# Nadu RCS sites carry on every page. Each pattern must match the entire line, so ordinary
# sentences that merely mention these words (for example "Maintenance of records") stay.
_BOILERPLATE_LINES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"Go to Main Content\b.*",
        r"Government of India",
        r"Registration of New MSCS",
        r"Ministry of Cooperation\s+CR Login\b.*",
        r"Central Registrar of Cooperative Societies\s+Login\b.*",
        r"Home\s*/\s*[\w &-]{1,40}",
        r"Last updated\s*:\s*\d{1,2}\s+\w+\s+\d{4}",
        r"Home\s+State Registrars\b.*\bContact us",
        r"Terms & Conditions\b.*",
        r"©\s*Content Owned by\b.*",
        r"Disclaimer\s+Web Information Manager.*",
        r"OFFICE OF THE REGISTRAR OF COOPERATIVE SOCIETIES\s+USEFUL LINKS.*",
        r"NVN Natarajan Maligai",
        r"No\.\s*170,\s*Periyar E\.V\.R\. High Road",
        r"Kilpauk Chennai\s*-\s*600\s*010",
        r"Phone No\.?\s*:\s*[\d\- ]+",
        r"Paniyaalar Naal\b.*",
        r"Email id\s*:\s*\S+@\S+",
        r"VERGAL Contact Us",
        r"Copyright\s*©.*",
        r"designed by Trophy systems",
    )
]

# Words that end in a full stop without ending the sentence. Initialisms such as "G.O.",
# "e.g." and "w.e.f." are recognised by their shape (see _ends_sentence).
_ABBREVIATIONS = frozenset(
    {
        "no.", "nos.", "sec.", "secs.", "s.", "u/s.", "rs.", "dr.", "mr.", "mrs.", "ms.",
        "shri.", "smt.", "art.", "cl.", "sl.", "vs.", "viz.", "etc.", "approx.", "dt.",
        "govt.", "dept.", "ltd.", "co.", "st.",
    }
)  # fmt: skip
_INITIALISM = re.compile(r"^(?:[A-Za-z]\.){2,}$")
_SENTENCE_END = (".", "!", "?", "।")  # the last is the Devanagari danda
_NUMBERED_HEADING = re.compile(r"^\d{1,3}[A-Z]?\.\s+[A-Z][^\n]{0,100}$")
_NAMED_HEADING = re.compile(r"^(?:CHAPTER|PART|SCHEDULE|ARTICLE|SECTION)\s+[\dIVXLC]+\b.*$")


def is_pdf(path: Path) -> bool:
    """True if the file exists and starts with the PDF signature.

    Catches HTML error pages and other files saved with a .pdf name, which the PDF reader
    would otherwise choke on. A missing or unreadable file is simply "not a PDF".
    """
    try:
        with open(path, "rb") as handle:
            return handle.read(len(PDF_MAGIC)) == PDF_MAGIC
    except OSError:
        return False


def is_mostly_glyph_garbage(text: str) -> bool:
    """True if font garbage ("(cid:N)" tokens, icon-font glyphs) makes up most of the text.

    pdfplumber returns this for PDFs whose fonts have no Unicode map. A stray token in a
    normal page does not count; that text is cleaned, not read again.
    """
    visible = len("".join(text.split()))
    if visible == 0:
        return False
    garbage = sum(len(match.group()) for match in _CID_TOKEN.finditer(text))
    garbage += len(_PRIVATE_USE.findall(text))
    return garbage / visible >= GLYPH_GARBAGE_SHARE


def clean_page_text(text: str) -> str:
    """Remove font garbage and web-page boilerplate lines from one page of extracted text.

    Spaces inside a line are left as they are, so removing "(cid:N)" never joins two words.
    """
    text = _PRIVATE_USE.sub("", _CID_TOKEN.sub("", text))
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.fullmatch(stripped) for pattern in _BOILERPLATE_LINES):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept)


@lru_cache(maxsize=2)
def _pypdf_reader(path: str):
    from pypdf import PdfReader  # imported here: CI has no ML packages

    return PdfReader(path)


def extract_page_pypdf(path: Path, page_index: int) -> str:
    """The text of one page (0-based) read with pypdf, or "" if pypdf cannot read it.

    The fallback for pages where pdfplumber returns font garbage. Never raises.
    """
    try:
        return _pypdf_reader(str(path)).pages[page_index].extract_text() or ""
    except Exception:  # pypdf not installed, damaged PDF, no such page
        return ""


def is_heading(line: str) -> bool:
    """True for a section heading ("32. General meetings." or "CHAPTER IV: ...") or an
    all-capitals title line. A heading is kept together with the text that follows it."""
    line = line.strip()
    if not line or len(line) > 120:
        return False
    if _NUMBERED_HEADING.match(line) or _NAMED_HEADING.match(line):
        return True
    return line.isupper() and len(line) <= 80


def _ends_sentence(word: str, next_word: str) -> bool:
    if not word.endswith(_SENTENCE_END):
        return False
    if word.lower() in _ABBREVIATIONS or _INITIALISM.match(word):
        return False
    # A sentence goes on into a lower-case word; scripts without case always start a new one.
    return not next_word.lstrip("\"'([")[:1].islower()


def split_sentences(text: str) -> list[tuple[str, bool]]:
    """Split text into (unit, is_heading) pairs: one per sentence, one per heading line.

    Line breaks inside a paragraph are PDF line wraps, so they do not end a sentence; a
    heading line does. Abbreviations such as "G.O.", "No." and "e.g." do not end one either.
    """
    units: list[tuple[str, bool]] = []
    paragraph: list[str] = []

    def flush() -> None:
        words = " ".join(paragraph).split()
        paragraph.clear()
        start = 0
        for i, word in enumerate(words):
            if i == len(words) - 1 or _ends_sentence(word, words[i + 1]):
                units.append((" ".join(words[start : i + 1]), False))
                start = i + 1

    for line in text.splitlines():
        if is_heading(line):
            flush()
            units.append((" ".join(line.split()), True))
        elif line.strip():
            paragraph.append(line.strip())
    flush()
    return units


def split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """Split a sentence longer than max_chars at word boundaries, into pieces of at most
    max_chars. A single word longer than max_chars is cut, as a last resort."""
    pieces: list[str] = []
    current = ""
    for word in sentence.split():
        while len(word) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:max_chars])
            word = word[max_chars:]
        if current and len(current) + 1 + len(word) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
    tail_merge_chars: int = DEFAULT_TAIL_MERGE_CHARS,
) -> list[str]:
    """Split text into chunks of whole sentences, each at most max_chars long.

    - A sentence longer than max_chars is split at word boundaries; a word is never cut
      (except one longer than max_chars).
    - A chunk starts with the last sentence of the chunk before it, when that sentence is
      at most half of max_chars, so a fact on a boundary appears whole in one chunk.
    - A heading never ends a chunk; it moves on to start the next one.
    - A last chunk whose new text is at most tail_merge_chars is merged into the one before.
    - A chunk shorter than min_chars is dropped.
    """
    units: list[tuple[str, bool]] = []
    for sentence, heading in split_sentences(text):
        if len(sentence) > max_chars:
            units.extend((piece, False) for piece in split_long_sentence(sentence, max_chars))
        else:
            units.append((sentence, heading))

    def size(*parts: list[str]) -> int:
        return len(" ".join(part for group in parts for part in group))

    # Each chunk is (sentences carried over from the previous chunk, its own new sentences).
    chunks: list[tuple[list[str], list[str]]] = []
    overlap: list[str] = []
    new: list[tuple[str, bool]] = []
    for sentence, heading in units:
        if new and size(overlap, [s for s, _ in new], [sentence]) > max_chars:
            moved = [new.pop()] if new[-1][1] and len(new) > 1 else []
            texts = [s for s, _ in new]
            chunks.append((overlap, texts))
            overlap = texts[-1:] if texts and len(texts[-1]) <= max_chars // 2 else []
            new = moved
            if overlap and size(overlap, [s for s, _ in new], [sentence]) > max_chars:
                overlap = []
        new.append((sentence, heading))
    if new:
        chunks.append((overlap, [s for s, _ in new]))

    if len(chunks) > 1 and size(chunks[-1][1]) <= tail_merge_chars:
        _, last_new = chunks.pop()
        previous_overlap, previous_new = chunks[-1]
        chunks[-1] = (previous_overlap, previous_new + last_new)

    joined = (" ".join([*carried, *own]) for carried, own in chunks)
    return [chunk for chunk in joined if len(chunk) >= min_chars]


def embedding_input(text: str) -> str:
    """The string to embed for a stored chunk text (adds the e5 "passage: " prefix)."""
    return f"{PASSAGE_PREFIX}{text}"


def build_chunk_payload(
    document: Document,
    page: int | None,
    text: str,
) -> dict:
    """Build standardized chunk payload dictionary for Qdrant storage.

    ``text`` is the clean chunk text. It is stored without the "passage: " prefix, so a
    retrieved Passage.text never starts with it and matches the Chunk row exactly.
    """
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
            raise CommandError(f"sources.csv not found at {csv_path}!")

        self.stdout.write(f"Reading {csv_path} and processing corpus...")

        documents_processed = 0
        chunks_written = 0
        vectors_upserted = 0
        # use_in_corpus=Y documents that produced nothing: (doc_id, why)
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

                # local_path is relative to backend/ (/app in the container); on a dev
                # machine it is usually relative to the repository root.
                pdf_file = settings.BASE_DIR / local_path if local_path else None
                if pdf_file is None or not pdf_file.is_file():
                    pdf_file = Path(settings.BASE_DIR).parent / local_path if local_path else None
                if pdf_file is None or not pdf_file.is_file():
                    self.stdout.write(
                        self.style.WARNING(f"PDF file not found for {doc_id}: {local_path!r}")
                    )
                    problems.append((doc_id, f"PDF not found ({local_path or 'no local_path'})"))
                    continue

                if not is_pdf(pdf_file):
                    self.stdout.write(
                        self.style.WARNING(f"Skipping {doc_id}: {pdf_file.name} is not a PDF")
                    )
                    problems.append((doc_id, f"not a PDF (no %PDF- header): {local_path}"))
                    continue

                self.stdout.write(f"Processing PDF for document: {doc_id}...")

                # Read the whole PDF first, so an unreadable file changes nothing. Only the
                # read is guarded: a failure while writing below must raise, not be swallowed.
                pages_and_chunks: list[tuple[int, str]] = []
                try:
                    with pdfplumber.open(pdf_file) as pdf:
                        for page_num, page in enumerate(pdf.pages, start=1):
                            raw_text = page.extract_text() or ""
                            # Fonts without a Unicode map come out as "(cid:N)" garbage;
                            # pypdf often reads those pages correctly.
                            if is_mostly_glyph_garbage(raw_text):
                                fallback = extract_page_pypdf(pdf_file, page_num - 1)
                                if fallback and not is_mostly_glyph_garbage(fallback):
                                    raw_text = fallback
                            page_text = clean_page_text(raw_text)
                            if not page_text:
                                continue
                            for chunk_str in chunk_text(
                                page_text,
                                max_chars=settings.CHUNK_MAX_CHARS,
                                min_chars=settings.CHUNK_MIN_CHARS,
                                tail_merge_chars=settings.CHUNK_TAIL_MERGE_CHARS,
                            ):
                                pages_and_chunks.append((page_num, chunk_str))
                except Exception as exc:  # corrupt or encrypted PDF
                    self.stdout.write(
                        self.style.WARNING(f"Could not read the PDF for {doc_id}: {exc}")
                    )
                    problems.append((doc_id, f"PDF could not be read ({exc.__class__.__name__})"))
                    continue

                documents_processed += 1
                if not pages_and_chunks:
                    # Nothing to write: keep whatever this document already has.
                    problems.append((doc_id, "PDF yielded zero chunks (scanned, no text?)"))
                    continue

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

                # Everything is read and embedded; only now replace the old chunks. The
                # PostgreSQL part is one transaction, so a failed write keeps the old rows.
                with transaction.atomic():
                    # Clear existing chunks for this doc to prevent duplication on re-runs
                    Chunk.objects.filter(document=document).delete()
                    Chunk.objects.bulk_create(chunk_records)
                    chunks_written += len(chunk_records)
                    self.stdout.write(
                        f"Saved {len(chunk_records)} chunks to PostgreSQL for {doc_id}."
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
