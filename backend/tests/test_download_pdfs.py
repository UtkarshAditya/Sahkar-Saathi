"""scripts/download_pdfs.py: TLS verification on by default, --insecure loud, final counts.
A local HTTP server stands in for the government sites: no internet."""

import importlib.util
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from django.conf import settings

SCRIPT = Path(settings.BASE_DIR).parent / "scripts" / "download_pdfs.py"


def load_script():
    spec = importlib.util.spec_from_file_location("download_pdfs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"%PDF-1.4 fake" if self.path.startswith("/ok.pdf") else b"<html>not a pdf</html>"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_downloads_skips_valid_files_and_reports_counts(server, tmp_path, capsys):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "have.pdf").write_bytes(b"%PDF-already here")
    rows = [
        ("OK", f"{server}/ok.pdf", "data/raw/ok.pdf"),
        ("HTML", f"{server}/bad.pdf", "data/raw/bad.pdf"),  # answers with a web page
        ("HAVE", f"{server}/ok.pdf", "data/raw/have.pdf"),  # a valid file is already there
        ("PAGE", "https://example.org/page", "data/raw/page.pdf"),  # no direct PDF link
        ("NOFILE", f"{server}/ok.pdf", ""),  # no PDF wanted
    ]
    sources = tmp_path / "sources.csv"
    sources.write_text(
        "doc_id,source_url,local_path\n" + "".join(f"{a},{b},{c}\n" for a, b, c in rows),
        encoding="utf-8",
    )

    code = load_script().main(["--sources", str(sources)])

    out = capsys.readouterr().out
    assert code == 1, "a failed download is a non-zero exit"
    assert "downloaded 1, skipped (already valid) 1, failed 1, no direct PDF link 1" in out
    assert (tmp_path / "raw" / "ok.pdf").read_bytes().startswith(b"%PDF")
    assert not (tmp_path / "raw" / "bad.pdf").exists()
    assert not list((tmp_path / "raw").glob("*.part")), "no cut-off download is left behind"
    assert (tmp_path / "raw" / "have.pdf").read_bytes() == b"%PDF-already here"


def test_certificates_are_verified_unless_insecure_is_given(capsys):
    module = load_script()
    strict = module.tls_context(insecure=False)
    assert strict.verify_mode == ssl.CERT_REQUIRED and strict.check_hostname is True
    assert capsys.readouterr().err == ""

    loose = module.tls_context(insecure=True)
    assert loose.verify_mode == ssl.CERT_NONE and loose.check_hostname is False
    assert "--insecure turns OFF TLS certificate verification" in capsys.readouterr().err


# --- --only-corpus and --missing ---------------------------------------------------------

CSV_HEADER = "doc_id,use_in_corpus,source_url,local_path\n"


def write_sources(tmp_path, rows):
    """rows: (doc_id, use_in_corpus, source_url, local_path). Returns the CSV path."""
    sources = tmp_path / "sources.csv"
    sources.write_text(CSV_HEADER + "".join(",".join(row) + "\n" for row in rows), encoding="utf-8")
    (tmp_path / "raw").mkdir(exist_ok=True)
    return sources


def test_only_corpus_downloads_just_the_y_rows(server, tmp_path, capsys):
    sources = write_sources(
        tmp_path,
        [
            ("YES", "Y", f"{server}/ok.pdf", "data/raw/yes.pdf"),
            ("HOLD", "Hold", f"{server}/ok.pdf", "data/raw/hold.pdf"),
            ("NO", "N", f"{server}/ok.pdf", "data/raw/no.pdf"),
            ("LOWER", "y", f"{server}/ok.pdf", "data/raw/lower.pdf"),
        ],
    )
    code = load_script().main(["--sources", str(sources), "--only-corpus"])
    out = capsys.readouterr().out
    assert code == 0 and "downloaded 2," in out
    assert sorted(p.name for p in (tmp_path / "raw").glob("*.pdf")) == ["lower.pdf", "yes.pdf"]


def test_without_only_corpus_every_pdf_row_is_downloaded(server, tmp_path, capsys):
    sources = write_sources(
        tmp_path,
        [
            ("YES", "Y", f"{server}/ok.pdf", "data/raw/yes.pdf"),
            ("HOLD", "Hold", f"{server}/ok.pdf", "data/raw/hold.pdf"),
        ],
    )
    load_script().main(["--sources", str(sources)])
    assert "downloaded 2," in capsys.readouterr().out


def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("--missing must not touch the network")

    monkeypatch.setattr("urllib.request.urlopen", refuse)


def test_missing_lists_what_is_absent_and_how_to_get_it(tmp_path, capsys, monkeypatch):
    no_network(monkeypatch)
    sources = write_sources(
        tmp_path,
        [
            ("HAVE", "Y", "https://example.org/have.pdf", "data/raw/have.pdf"),
            ("DIRECT", "Y", "https://example.org/files/direct.pdf?x=1", "data/raw/direct.pdf"),
            ("PAGE", "Hold", "https://example.org/page.aspx?id=3", "data/raw/page.pdf"),
            ("NOURL", "N", "", "data/raw/nourl.pdf"),
            ("HTML", "Y", "https://example.org/faq", "data/raw/faq.html"),
            ("NOPATH", "Y", "https://example.org/x.pdf", ""),  # nothing is expected: not listed
        ],
    )
    (tmp_path / "raw" / "have.pdf").write_bytes(b"%PDF-1.4 here")

    code = load_script().main(["--sources", str(sources), "--missing"])
    out = capsys.readouterr().out

    assert code == 0
    assert "4 of 5 expected files are missing or unusable" in out
    rows = {line.split()[0]: line for line in out.splitlines() if line[:2].isupper()}
    assert "HAVE" not in rows and "NOPATH" not in rows
    assert (
        "direct PDF link" in rows["DIRECT"]
        and "https://example.org/files/direct.pdf" in rows["DIRECT"]
    )
    assert "web page: print to PDF by hand" in rows["PAGE"] and "Hold" in rows["PAGE"]
    assert "no URL: get it from the Drive" in rows["NOURL"]
    assert "web page: print to PDF by hand" in rows["HTML"]
    assert "data/raw/direct.pdf" in rows["DIRECT"], "the expected local_path is shown"
    assert "2 of them have use_in_corpus=Y" in out and "1 have a direct PDF link" in out
    assert "local_path that is not a .pdf (HTML)" in out
    assert list((tmp_path / "raw").iterdir()) == [tmp_path / "raw" / "have.pdf"], "nothing written"


def test_missing_catches_a_file_that_is_not_a_pdf_and_a_name_that_differs_in_case(
    tmp_path, capsys, monkeypatch
):
    no_network(monkeypatch)
    sources = write_sources(
        tmp_path,
        [
            ("TEXT", "Y", "https://example.org/a.pdf", "data/raw/text.pdf"),
            ("CASE", "Y", "https://example.org/b.pdf", "data/raw/case.pdf"),
        ],
    )
    (tmp_path / "raw" / "text.pdf").write_text("this is not a pdf")
    (tmp_path / "raw" / "Case.pdf").write_bytes(b"%PDF-1.4 here")  # the CSV says case.pdf

    load_script().main(["--sources", str(sources), "--missing"])
    out = capsys.readouterr().out
    assert "file is not a PDF" in out
    assert "named 'Case.pdf' (case differs)" in out, "a Windows-only match would fail in Docker"
    assert "2 of 2 expected files are missing or unusable" in out


def test_missing_with_only_corpus_skips_the_other_rows(tmp_path, capsys, monkeypatch):
    no_network(monkeypatch)
    sources = write_sources(
        tmp_path,
        [
            ("YES", "Y", "https://example.org/a.pdf", "data/raw/yes.pdf"),
            ("HOLD", "Hold", "https://example.org/b.pdf", "data/raw/hold.pdf"),
            ("NO", "N", "https://example.org/c.pdf", "data/raw/no.pdf"),
        ],
    )
    load_script().main(["--sources", str(sources), "--missing", "--only-corpus"])
    out = capsys.readouterr().out
    assert "1 of 1 expected files are missing" in out
    assert "YES" in out and "HOLD" not in out and "NO " not in out


def test_missing_says_so_when_nothing_is_missing(tmp_path, capsys, monkeypatch):
    no_network(monkeypatch)
    sources = write_sources(
        tmp_path, [("HAVE", "Y", "https://example.org/a.pdf", "data/raw/have.pdf")]
    )
    (tmp_path / "raw" / "have.pdf").write_bytes(b"%PDF-1.4 here")
    assert load_script().main(["--sources", str(sources), "--missing"]) == 0
    assert "Every one of the 1 expected files is in" in capsys.readouterr().out


def test_missing_never_creates_the_raw_folder_or_the_tls_context(tmp_path, monkeypatch):
    no_network(monkeypatch)
    module = load_script()

    def refuse(insecure):
        raise AssertionError("--missing needs no TLS context")

    monkeypatch.setattr(module, "tls_context", refuse)
    sources = tmp_path / "sources.csv"
    sources.write_text(CSV_HEADER + "A,Y,https://example.org/a.pdf,data/raw/a.pdf\n")
    assert module.main(["--sources", str(sources), "--missing", "--insecure"]) == 0
    assert not (tmp_path / "raw").exists()


def test_insecure_is_off_unless_the_flag_is_given(tmp_path, monkeypatch):
    module = load_script()
    seen = []

    def spy(insecure):
        seen.append(insecure)
        return ssl.create_default_context()

    monkeypatch.setattr(module, "tls_context", spy)
    sources = tmp_path / "sources.csv"
    sources.write_text("doc_id,source_url,local_path\n", encoding="utf-8")
    assert module.main(["--sources", str(sources)]) == 0
    assert module.main(["--sources", str(sources), "--insecure"]) == 0
    assert seen == [False, True]
