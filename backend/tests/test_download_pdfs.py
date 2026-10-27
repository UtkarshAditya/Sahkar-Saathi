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
