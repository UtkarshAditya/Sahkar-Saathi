"""scripts/expand_corpus.py: report-only by default; Y becomes N only with --demote-missing."""

import importlib.util
import sys
from pathlib import Path

import pytest
from django.conf import settings

SCRIPT = Path(settings.BASE_DIR).parent / "scripts" / "expand_corpus.py"
HEADER = "doc_id,local_path,use_in_corpus\n"


def load_script():
    spec = importlib.util.spec_from_file_location("expand_corpus", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks the module up here
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(tmp_path):
    """data/raw with one good PDF and one HTML page named .pdf; a CSV marking both Y,
    plus a Y row whose file is missing."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "GOOD_en.pdf").write_bytes(b"%PDF-1.4 ok")
    (raw / "BAD_en.pdf").write_bytes(b"<html>404</html>")
    csv_path = tmp_path / "data" / "sources.csv"
    csv_path.write_text(
        HEADER
        + "GOOD,data/raw/GOOD_en.pdf,Y\n"
        + "BAD,data/raw/BAD_en.pdf,Y\n"
        + "GONE,data/raw/GONE_en.pdf,Y\n",
        encoding="utf-8",
    )
    return tmp_path, raw, csv_path


def run(module, tmp_path, raw, csv_path, **flags):
    inspections = module.inspect_raw_pdfs(raw)
    return module.update_sources_csv(csv_path, inspections, tmp_path, **flags)


def test_default_run_only_reports(corpus, capsys):
    tmp_path, raw, csv_path = corpus
    before = csv_path.read_text(encoding="utf-8")

    run(load_script(), tmp_path, raw, csv_path)

    assert csv_path.read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "BAD" in out and "GONE" in out and "still Y" in out


def test_write_without_demote_never_turns_y_into_n(corpus):
    tmp_path, raw, csv_path = corpus
    before = csv_path.read_text(encoding="utf-8")

    run(load_script(), tmp_path, raw, csv_path, write=True)

    assert csv_path.read_text(encoding="utf-8") == before


def test_demote_missing_changes_only_the_bad_rows(corpus):
    tmp_path, raw, csv_path = corpus

    run(load_script(), tmp_path, raw, csv_path, write=True, demote_missing=True)

    rows = {
        r.split(",")[0]: r.rstrip("\r\n").split(",")[2]
        for r in csv_path.read_text(encoding="utf-8").splitlines()[1:]
    }
    assert rows == {"GOOD": "Y", "BAD": "N", "GONE": "N"}


def test_demote_missing_alone_does_not_write(corpus):
    tmp_path, raw, csv_path = corpus
    before = csv_path.read_text(encoding="utf-8")

    run(load_script(), tmp_path, raw, csv_path, demote_missing=True)

    assert csv_path.read_text(encoding="utf-8") == before


def test_main_without_write_never_runs_docker(corpus, monkeypatch):
    tmp_path, raw, csv_path = corpus
    module = load_script()
    monkeypatch.setattr(module, "ROOT", tmp_path)

    def no_docker(*args, **kwargs):
        raise AssertionError("docker must not run without --write")

    monkeypatch.setattr(module.subprocess, "Popen", no_docker)

    rc = module.main(["--raw-dir", str(raw), "--sources-csv", str(csv_path)])

    assert rc == 0
