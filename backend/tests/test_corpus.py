"""corpus_status and ingest_corpus, with fake ML packages: no network, no model, no Qdrant."""

import io
import sys
import types
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.management.commands.ingest_corpus import (
    PASSAGE_PREFIX,
    build_chunk_payload,
    embedding_input,
)
from apps.knowledge.models import Chunk, Document

COLLECTION = "sahkar_saathi_chunks"


def make_document(doc_id: str, state: str = "central") -> Document:
    return Document.objects.create(
        id=doc_id,
        title=f"Title of {doc_id}",
        publisher="Test publisher",
        doc_type="act",
        state=state,
        language="en",
        published_date=date(2024, 1, 1),
        version="1",
    )


def make_chunk(document: Document, n: int) -> Chunk:
    return Chunk.objects.create(
        document=document,
        text=f"chunk {n}",
        page=n,
        state=document.state,
        language=document.language,
        vector_id=f"{document.id}-{n}",
    )


class Bag:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def install_fake_qdrant(monkeypatch, *, points=0, collections=(COLLECTION,), error=None):
    """Put a fake qdrant_client in sys.modules. Returns what the fake client received."""
    seen = types.SimpleNamespace(urls=[], upserted=[], deleted=[], created=[])

    class FakeClient:
        def __init__(self, url=None, **kwargs):
            seen.urls.append(url)

        def get_collections(self):
            if error:
                raise error
            return types.SimpleNamespace(collections=[Bag(name=n) for n in collections])

        def count(self, collection_name, exact=True):
            return types.SimpleNamespace(count=points)

        def create_collection(self, **kwargs):
            seen.created.append(kwargs["collection_name"])

        def delete(self, **kwargs):
            seen.deleted.append(kwargs["collection_name"])

        def upsert(self, collection_name, points):
            seen.upserted.extend(points)

    models = types.ModuleType("qdrant_client.http.models")
    for name in ["VectorParams", "PointStruct", "FilterSelector", "Filter", "FieldCondition"]:
        setattr(models, name, type(name, (Bag,), {}))
    models.MatchValue = type("MatchValue", (Bag,), {})
    models.Distance = Bag(COSINE="Cosine")
    http = types.ModuleType("qdrant_client.http")
    http.models = models
    package = types.ModuleType("qdrant_client")
    package.QdrantClient = FakeClient
    package.http = http
    monkeypatch.setitem(sys.modules, "qdrant_client", package)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http)
    monkeypatch.setitem(sys.modules, "qdrant_client.http.models", models)
    return seen


def run(command: str, *args: str) -> str:
    out = io.StringIO()
    call_command(command, *args, stdout=out)
    return out.getvalue()


# --- corpus_status --------------------------------------------------------------------


def test_corpus_status_lists_chunks_per_document_and_the_qdrant_count(monkeypatch, settings):
    settings.QDRANT_URL = "http://qdrant.test:6333"
    seen = install_fake_qdrant(monkeypatch, points=3)
    a = make_document("DOC-A", state="TN")
    make_document("DOC-B")
    for n in (1, 2, 3):
        make_chunk(a, n)
    make_document("DOC-EMPTY")

    out = run("corpus_status")

    assert seen.urls == ["http://qdrant.test:6333"]
    lines = {line.split()[0]: line for line in out.splitlines() if line.startswith("DOC-")}
    assert lines["DOC-A"].split() == ["DOC-A", "TN", "3"]
    assert lines["DOC-B"].split() == ["DOC-B", "central", "0"]
    assert "Documents: 3   Chunk rows: 3" in out
    assert f"Qdrant collection '{COLLECTION}': 3" in out
    assert "Documents with zero chunks (2)" in out
    assert "  DOC-B" in out and "  DOC-EMPTY" in out
    assert "Run ingest_corpus again" not in out


def test_corpus_status_warns_when_postgres_and_qdrant_disagree(monkeypatch):
    install_fake_qdrant(monkeypatch, points=5)
    make_chunk(make_document("DOC-A"), 1)
    out = run("corpus_status")
    assert "PostgreSQL has 1 chunk rows but Qdrant has 5 points" in out
    assert "Every document has chunks." in out


def test_corpus_status_says_when_qdrant_is_not_reachable(monkeypatch):
    install_fake_qdrant(monkeypatch, error=ConnectionError("refused"))
    make_document("DOC-A")
    out = run("corpus_status")
    assert "Qdrant not reachable" in out
    assert "DOC-A" in out, "the database part still prints"


def test_corpus_status_tolerates_a_missing_qdrant_client(monkeypatch):
    monkeypatch.setitem(sys.modules, "qdrant_client", None)  # the import fails
    out = run("corpus_status")
    assert "qdrant-client is not installed" in out


def test_corpus_status_collection_option(monkeypatch):
    install_fake_qdrant(monkeypatch, collections=("other",), points=0)
    assert "collection does not exist yet" in run("corpus_status")
    assert "Qdrant collection 'other': 0" in run("corpus_status", "--collection", "other")


# --- the payload helper ---------------------------------------------------------------


def _document() -> Document:
    return Document(
        id="DOC-X",
        title="T",
        publisher="P",
        doc_type="act",
        state="TN",
        language="en",
        published_date=None,
        version="1",
    )


@pytest.mark.parametrize("text", ["plain text", f"{PASSAGE_PREFIX}already prefixed"])
def test_the_payload_text_never_starts_with_the_passage_prefix(text):
    payload = build_chunk_payload(_document(), 3, text)
    assert not payload["text"].startswith(PASSAGE_PREFIX)
    assert payload["text"] == text.removeprefix(PASSAGE_PREFIX)
    assert payload["doc_id"] == "DOC-X" and payload["page"] == 3 and payload["state"] == "TN"
    assert payload["published_date"] is None


def test_the_prefix_is_only_added_to_the_embedded_string():
    assert embedding_input("hello") == "passage: hello"


# --- ingest_corpus, end to end with fakes ---------------------------------------------


@pytest.fixture
def ingest(monkeypatch, tmp_path):
    """Fake pdfplumber, sentence-transformers and Qdrant; a sources.csv written per test."""
    seen = install_fake_qdrant(monkeypatch)
    seen.embedded = []
    pdf_text: dict[str, str] = {}

    class FakeVector:
        def tolist(self):
            return [0.1, 0.2, 0.3]

    class FakeModel:
        def __init__(self, name):
            pass

        def get_embedding_dimension(self):
            return 3

        def encode(self, text):
            seen.embedded.append(text)
            return FakeVector()

    class FakePdf:
        def __init__(self, path):
            self.pages = [Bag(extract_text=lambda text=pdf_text[str(path)]: text)]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    st = types.ModuleType("sentence_transformers")
    st.SentenceTransformer = FakeModel
    pdfplumber = types.ModuleType("pdfplumber")
    pdfplumber.open = FakePdf
    monkeypatch.setitem(sys.modules, "sentence_transformers", st)
    monkeypatch.setitem(sys.modules, "pdfplumber", pdfplumber)

    def add_pdf(name: str, text: str) -> str:
        path = tmp_path / name
        path.write_bytes(b"%PDF-fake")
        pdf_text[str(path)] = text
        return str(path)

    def write_csv(rows: list[tuple[str, str, str]]) -> None:
        lines = ["doc_id,use_in_corpus,local_path"]
        lines += [f'{doc_id},{use},"{path}"' for doc_id, use, path in rows]
        csv_path = tmp_path / "sources.csv"
        csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        monkeypatch.setenv("SOURCES_CSV", str(csv_path))

    seen.add_pdf = add_pdf
    seen.write_csv = write_csv
    return seen


def test_ingest_stores_clean_text_and_reports_every_problem(ingest):
    long_text = "cooperative society rule " * 120  # about 3,000 characters: several chunks
    for doc_id in ("DOC-A", "DOC-B", "DOC-C"):
        make_document(doc_id)
    ingest.write_csv(
        [
            ("DOC-A", "Y", ingest.add_pdf("a.pdf", long_text)),
            ("DOC-B", "Y", ingest.add_pdf("b.pdf", "")),  # no text: zero chunks
            ("DOC-C", "Y", "does/not/exist.pdf"),  # missing PDF
            ("DOC-D", "Y", ingest.add_pdf("d.pdf", "text")),  # no Document row
            ("DOC-E", "N", "ignored.pdf"),  # not in the corpus
        ]
    )

    out = run("ingest_corpus")

    chunks = list(Chunk.objects.filter(document_id="DOC-A"))
    assert len(chunks) >= 3
    assert not Chunk.objects.exclude(document_id="DOC-A").exists()

    # Chunk rows and Qdrant payloads hold identical, clean text; only the embedded input
    # carries the "passage: " prefix.
    payload_texts = sorted(p.payload["text"] for p in ingest.upserted)
    assert payload_texts == sorted(c.text for c in chunks)
    assert not any(t.startswith(PASSAGE_PREFIX) for t in payload_texts)
    assert ingest.embedded and all(t.startswith(PASSAGE_PREFIX) for t in ingest.embedded)

    n = len(chunks)
    assert f"documents processed 2, chunks written {n}, vectors upserted {n}" in out
    assert "3 use_in_corpus=Y document(s) need attention" in out
    assert "DOC-B: PDF yielded zero chunks" in out
    assert "DOC-C: PDF not found" in out
    assert "DOC-D: no Document row" in out
    assert "DOC-E" not in out


def test_ingest_fails_when_no_chunk_was_written(ingest):
    make_document("DOC-B")
    ingest.write_csv([("DOC-B", "Y", ingest.add_pdf("b.pdf", ""))])
    with pytest.raises(CommandError, match="No chunks were written"):
        run("ingest_corpus")


def test_ingest_fails_clearly_when_sources_csv_is_missing(ingest, monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCES_CSV", str(tmp_path / "missing.csv"))
    with pytest.raises(CommandError, match="sources.csv not found"):
        run("ingest_corpus")


def test_ingest_explains_missing_ml_packages(monkeypatch):
    monkeypatch.setitem(sys.modules, "pdfplumber", None)  # the import fails
    with pytest.raises(CommandError, match="INSTALL_ML=true"):
        run("ingest_corpus")
