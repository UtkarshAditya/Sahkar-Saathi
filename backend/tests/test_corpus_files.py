"""corpus_status --files: does each use_in_corpus=Y row have its PDF, and is it readable text?
Fake PDF files and a fake pdfplumber (or none): no ML packages, no network."""

import io
import sys
import types

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.management.commands import corpus_status

HEADER = "doc_id,use_in_corpus,local_path\n"


@pytest.fixture
def no_pdfplumber(monkeypatch):
    monkeypatch.setitem(sys.modules, "pdfplumber", None)  # `import pdfplumber` fails


@pytest.fixture
def fake_pdfplumber(monkeypatch):
    """A pdfplumber whose files hold the pages registered in ``texts`` (by file name)."""
    texts: dict[str, list[str] | Exception] = {}

    class FakePdf:
        def __init__(self, path):
            content = texts[path.name]
            if isinstance(content, Exception):
                raise content
            self.pages = [types.SimpleNamespace(extract_text=lambda t=t: t) for t in content]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    module = types.ModuleType("pdfplumber")
    module.open = lambda path: FakePdf(path)
    monkeypatch.setitem(sys.modules, "pdfplumber", module)
    return texts


def make_pdf(folder, name, content=b"%PDF-1.4 fake"):
    path = folder / name
    path.write_bytes(content)
    return path


def write_sources(tmp_path, monkeypatch, rows):
    """rows: (doc_id, use_in_corpus, path). Absolute paths are used as they are."""
    sources = tmp_path / "sources.csv"
    sources.write_text(HEADER + "".join(",".join(map(str, row)) + "\n" for row in rows))
    monkeypatch.setenv("SOURCES_CSV", str(sources))
    return sources


def report() -> str:
    out = io.StringIO()
    call_command("corpus_status", "--files", stdout=out)
    return out.getvalue()


def lines_by_doc(out: str) -> dict[str, str]:
    return {line.split()[0]: line for line in out.splitlines() if line[:3].isupper()}


def test_files_report_covers_present_missing_and_not_a_pdf(tmp_path, monkeypatch, no_pdfplumber):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_pdf(raw, "good.pdf")
    make_pdf(raw, "text.pdf", b"just some text, not a PDF")
    write_sources(
        tmp_path,
        monkeypatch,
        [
            ("GOOD", "Y", raw / "good.pdf"),
            ("TEXT", "Y", raw / "text.pdf"),
            ("GONE", "Y", raw / "gone.pdf"),
            ("PAGE", "Y", raw / "page.html"),
            ("HOLD", "Hold", raw / "hold.pdf"),
            ("NOPE", "N", raw / "nope.pdf"),
            ("EMPTY", "Y", ""),
        ],
    )

    out = report()
    rows = lines_by_doc(out)

    assert "5 rows with use_in_corpus=Y" in out
    assert "HOLD" not in rows and "NOPE" not in rows, "only Y rows are checked"
    assert rows["GOOD"].split()[1:3] == ["present", "yes"]
    assert rows["TEXT"].split()[1:3] == ["present", "NO"]
    assert "not a PDF" in rows["TEXT"]
    assert rows["GONE"].split()[1] == "MISSING" and "gone.pdf" in rows["GONE"]
    assert "[not a .pdf path" in rows["PAGE"]
    assert "no local_path" in rows["EMPTY"]
    assert "pdfplumber not installed" in out
    assert rows["GOOD"].split()[3:6] == ["n/a", "n/a", "n/a"], "no counts without pdfplumber"
    assert "Y documents: 5   files present: 2   files missing: 3   low-text files: 0" in out


def test_with_pdfplumber_pages_characters_and_low_text_are_reported(
    tmp_path, monkeypatch, fake_pdfplumber
):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in ("full.pdf", "scan.pdf", "broken.pdf", "empty.pdf"):
        make_pdf(raw, name)
    fake_pdfplumber["full.pdf"] = ["a" * 500, "b" * 700]  # 600 characters per page
    fake_pdfplumber["scan.pdf"] = ["x" * 10, "", "y" * 20]  # 10 per page: a scan
    fake_pdfplumber["broken.pdf"] = ValueError("not a real pdf")
    fake_pdfplumber["empty.pdf"] = []  # zero pages must not divide by zero
    names = ("full.pdf", "scan.pdf", "broken.pdf", "empty.pdf")
    write_sources(tmp_path, monkeypatch, [(n[:-4].upper(), "Y", raw / n) for n in names])

    out = report()
    rows = lines_by_doc(out)

    assert rows["FULL"].split()[3:6] == ["2", "1200", "600"]
    assert "LOW TEXT" not in rows["FULL"]
    assert rows["SCAN"].split()[3:6] == ["3", "30", "10"]
    assert "LOW TEXT: probably scanned" in rows["SCAN"]
    assert "unreadable (ValueError)" in rows["BROKEN"]
    assert rows["EMPTY"].split()[3:6] == ["0", "0", "0"] and "LOW TEXT" in rows["EMPTY"]
    assert "pdfplumber not installed" not in out
    assert "Y documents: 4   files present: 4   files missing: 0   low-text files: 2" in out


def test_the_boundary_is_100_characters_per_page(tmp_path, monkeypatch, fake_pdfplumber):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_pdf(raw, "edge.pdf")
    make_pdf(raw, "under.pdf")
    fake_pdfplumber["edge.pdf"] = ["e" * 100]
    fake_pdfplumber["under.pdf"] = ["u" * 99]
    rows = [("EDGE", "Y", raw / "edge.pdf"), ("UNDER", "Y", raw / "under.pdf")]
    write_sources(tmp_path, monkeypatch, rows)
    rows = lines_by_doc(report())
    assert "LOW TEXT" not in rows["EDGE"] and "LOW TEXT" in rows["UNDER"]


def test_a_name_that_differs_only_in_case_is_flagged(tmp_path, monkeypatch, no_pdfplumber):
    """A Windows-only match would fail in the Linux container, so it is reported."""
    raw = tmp_path / "raw"
    raw.mkdir()
    make_pdf(raw, "Mixed-Case.pdf")
    write_sources(tmp_path, monkeypatch, [("CASE", "Y", raw / "mixed-case.pdf")])
    out = report()
    row = lines_by_doc(out)["CASE"]
    assert row.split()[1] == "CASE" and "case differs: Mixed-Case.pdf" in row
    assert "files present: 0   files missing: 1" in out


def test_relative_paths_are_found_like_ingest_corpus_does(
    tmp_path, monkeypatch, settings, no_pdfplumber
):
    """backend/ first, then the repository root."""
    settings.BASE_DIR = tmp_path / "backend"
    (tmp_path / "backend" / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw").mkdir(parents=True)
    make_pdf(tmp_path / "backend" / "data" / "raw", "in-backend.pdf")
    make_pdf(tmp_path / "data" / "raw", "in-root.pdf")
    write_sources(
        tmp_path,
        monkeypatch,
        [
            ("BACKEND", "Y", "data/raw/in-backend.pdf"),
            ("ROOT", "Y", "data/raw/in-root.pdf"),
            ("NONE", "Y", "data/raw/none.pdf"),
        ],
    )
    out = report()
    rows = lines_by_doc(out)
    assert rows["BACKEND"].split()[1] == "present" and rows["ROOT"].split()[1] == "present"
    assert rows["NONE"].split()[1] == "MISSING"
    assert "files present: 2   files missing: 1" in out


def test_it_needs_neither_the_database_nor_qdrant(tmp_path, monkeypatch, no_pdfplumber):
    monkeypatch.setitem(sys.modules, "qdrant_client", None)
    write_sources(tmp_path, monkeypatch, [("A", "Y", tmp_path / "a.pdf")])
    out = report()
    assert "Qdrant" not in out and "Chunk rows" not in out


def test_a_missing_sources_csv_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCES_CSV", str(tmp_path / "nope.csv"))
    with pytest.raises(CommandError, match="sources.csv not found"):
        report()


def test_the_default_csv_path_follows_sources_csv_then_the_repository(
    tmp_path, monkeypatch, settings
):
    settings.BASE_DIR = tmp_path / "backend"
    (tmp_path / "backend").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sources.csv").write_text(HEADER)
    monkeypatch.delenv("SOURCES_CSV", raising=False)
    assert corpus_status.sources_csv_path() == tmp_path / "data" / "sources.csv"

    (tmp_path / "backend" / "data").mkdir()
    (tmp_path / "backend" / "data" / "sources.csv").write_text(HEADER)
    assert corpus_status.sources_csv_path() == tmp_path / "backend" / "data" / "sources.csv"

    monkeypatch.setenv("SOURCES_CSV", "/elsewhere/sources.csv")
    assert str(corpus_status.sources_csv_path()).endswith("sources.csv")
    assert "elsewhere" in str(corpus_status.sources_csv_path())


def test_the_committed_csv_can_be_checked_without_crashing(monkeypatch, no_pdfplumber):
    """Against the real data/sources.csv and data/raw: no assertions about what is present."""
    monkeypatch.delenv("SOURCES_CSV", raising=False)
    out = report()
    assert "rows with use_in_corpus=Y" in out and "Y documents:" in out
