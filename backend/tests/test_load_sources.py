"""`manage.py load_sources`: document metadata from the sources inventory CSV."""

import csv
import io
from datetime import date
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.models import Document

REAL_CSV = Path(settings.BASE_DIR).parent / "data" / "sources.csv"
HEADER = [
    "doc_id",
    "title",
    "publisher",
    "doc_type",
    "source_url",
    "published_date",
    "language",
    "state",
    "version",
    "status",
    "notes",
]


def row(**overrides) -> dict:
    base = {
        "doc_id": "CEN-TEST-ACT",
        "title": "Test Act, 2002",
        "publisher": "Test Publisher",
        "doc_type": "act",
        "source_url": "https://example.org/act.pdf",
        "published_date": "2025-06-27",
        "language": "en",
        "state": "central",
        "version": "1",
        "status": "active",
        "notes": "Long reviewer note that must never be printed.",
    }
    return base | overrides


def write_csv(path: Path, rows: list[dict], header: list[str] = HEADER) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def run(path: Path, *args: str) -> str:
    out = io.StringIO()
    call_command("load_sources", "--path", str(path), *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def csv_path(tmp_path):
    return tmp_path / "sources.csv"


def test_valid_rows_create_and_a_second_run_is_a_no_op(csv_path):
    write_csv(csv_path, [row(), row(doc_id="TN-TEST-RULES", doc_type="Rules", state="TN")])
    out = run(csv_path)
    assert "2 rows -> created 2, updated 0, unchanged 0, skipped 0" in out

    doc = Document.objects.get(pk="TN-TEST-RULES")
    assert doc.doc_type == "rules"  # a label, matched ignoring case, stores the value
    assert doc.state == "TN"
    assert doc.published_date == date(2025, 6, 27)
    assert doc.is_sample is False
    assert Document.objects.get(pk="CEN-TEST-ACT").source_url == "https://example.org/act.pdf"

    out = run(csv_path)
    assert "created 0, updated 0, unchanged 2, skipped 0" in out


def test_an_edited_cell_updates_the_row(csv_path):
    write_csv(csv_path, [row()])
    run(csv_path)
    write_csv(csv_path, [row(version="2", title="Test Act, 2002 (amended)")])
    out = run(csv_path)
    assert "created 0, updated 1, unchanged 0" in out
    doc = Document.objects.get(pk="CEN-TEST-ACT")
    assert (doc.version, doc.title) == ("2", "Test Act, 2002 (amended)")


def test_empty_published_date_loads_as_null_and_reruns_are_idempotent(csv_path):
    write_csv(csv_path, [row(published_date="")])
    assert "created 1, updated 0, unchanged 0, skipped 0" in run(csv_path)
    assert Document.objects.get(pk="CEN-TEST-ACT").published_date is None
    assert "created 0, updated 0, unchanged 1, skipped 0" in run(csv_path)


def test_published_date_column_is_optional(csv_path):
    write_csv(csv_path, [row()], [c for c in HEADER if c != "published_date"])
    assert "created 1, updated 0, unchanged 0, skipped 0" in run(csv_path)
    assert Document.objects.get(pk="CEN-TEST-ACT").published_date is None


def test_clearing_a_date_updates_the_row(csv_path):
    write_csv(csv_path, [row()])
    run(csv_path)
    write_csv(csv_path, [row(published_date="")])
    assert "created 0, updated 1, unchanged 0" in run(csv_path)
    assert Document.objects.get(pk="CEN-TEST-ACT").published_date is None


def test_extra_columns_are_ignored_and_never_printed(csv_path):
    header = [*HEADER, "licence", "verification"]
    write_csv(csv_path, [row(licence="CC-BY", verification="VERIFIED")], header)
    out = run(csv_path)
    assert "created 1" in out
    assert "reviewer note" not in out and "CC-BY" not in out


def test_source_url_column_is_optional(csv_path):
    write_csv(csv_path, [row()], [c for c in HEADER if c != "source_url"])
    run(csv_path)
    assert Document.objects.get(pk="CEN-TEST-ACT").source_url == ""


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"doc_type": "Parliamentary Q&A"}, "doc_type 'Parliamentary Q&A' is not a known type"),
        ({"doc_type": "ACT-X"}, "is not a known type"),
        ({"doc_type": "MODEL-BYLAWS"}, "is not a known type"),  # values are case-sensitive
        ({"status": "check_needed"}, "status 'check_needed' must be one of"),
        ({"status": "Active"}, "status 'Active' must be one of"),
        ({"state": "Tamil Nadu"}, "state 'Tamil Nadu' must be 'central' or a code like 'TN'"),
        ({"state": "TAMILNADU"}, "must be 'central' or a code like 'TN'"),
        ({"published_date": "2018"}, "published_date '2018' is not a YYYY-MM-DD date"),
        ({"published_date": "2026-02"}, "published_date '2026-02' is not a YYYY-MM-DD date"),
        ({"published_date": " "}, "published_date ' ' is not a YYYY-MM-DD date"),
        ({"published_date": "web page"}, "is not a YYYY-MM-DD date"),
        ({"published_date": "2025-02-30"}, "is not a YYYY-MM-DD date"),
        ({"published_date": "27/06/2025"}, "is not a YYYY-MM-DD date"),
        ({"doc_id": "CEN TEST"}, "may only use letters, digits"),
        ({"doc_id": "X" * 65}, "doc_id has 65 characters (max 64)"),
        ({"title": "T" * 301}, "title has 301 characters (max 300)"),
        ({"publisher": "P" * 201}, "publisher has 201 characters (max 200)"),
        ({"version": "V" * 51}, "version has 51 characters (max 50)"),
        ({"source_url": "https://example.org/" + "a" * 481}, "source_url has 501 characters"),
        ({"source_url": "not a url"}, "source_url is not a URL"),
        ({"language": "english-uk"}, "language has 10 characters (max 8)"),
        ({"title": ""}, "title is empty"),
        ({"publisher": "   "}, "publisher is empty"),
        ({"version": ""}, "version is empty"),
        ({"doc_id": ""}, "doc_id is empty"),
    ],
)
def test_invalid_rows_are_skipped_with_their_reason(csv_path, overrides, reason):
    write_csv(csv_path, [row(doc_id="GOOD-ROW"), row(**overrides)])
    out = run(csv_path)
    assert "created 1, updated 0, unchanged 0, skipped 1" in out
    assert "  line 3 " in out and reason in out
    assert "Skipped rows by reason" in out
    assert Document.objects.filter(pk="GOOD-ROW").exists()
    assert Document.objects.count() == 1  # nothing truncated or converted into the table


def test_one_row_reports_all_its_problems_and_reasons_are_grouped(csv_path):
    bad = {"doc_type": "Guidelines", "state": "Tamil Nadu"}
    write_csv(csv_path, [row(doc_id="A", **bad), row(doc_id="B", **bad), row(doc_id="C")])
    out = run(csv_path)
    assert (
        "line 2 A: doc_type 'Guidelines' is not a known type; "
        "state 'Tamil Nadu' must be 'central' or a code like 'TN'"
    ) in out
    assert "2  doc_type is not a known type ('Guidelines' x2)" in out
    assert "2  state is not 'central' or a short code ('Tamil Nadu' x2)" in out


def test_duplicate_ids_skip_every_copy(csv_path):
    write_csv(csv_path, [row(), row(title="Another title"), row(doc_id="OTHER")])
    out = run(csv_path)
    assert "created 1, updated 0, unchanged 0, skipped 2" in out
    assert "doc_id appears 2 times in the file" in out
    assert not Document.objects.filter(pk="CEN-TEST-ACT").exists()


def test_line_numbers_count_multiline_cells(csv_path):
    write_csv(csv_path, [row(doc_id="A", title="Two\nlines"), row(doc_id="B", status="draft")])
    out = run(csv_path)
    assert "line 4 B:" in out


def test_strict_writes_nothing_when_any_row_is_invalid(csv_path):
    write_csv(csv_path, [row(), row(doc_id="BAD", status="check_needed")])
    with pytest.raises(CommandError, match="nothing written"):
        run(csv_path, "--strict")
    assert not Document.objects.exists()

    write_csv(csv_path, [row()])
    run(csv_path, "--strict")
    assert Document.objects.count() == 1


def test_dry_run_writes_nothing(csv_path):
    write_csv(csv_path, [row(), row(doc_id="BAD", status="check_needed")])
    out = run(csv_path, "--dry-run")
    assert "dry run, nothing written" in out
    assert "created 1, updated 0, unchanged 0, skipped 1" in out
    assert not Document.objects.exists()


def test_missing_required_column_is_an_error(csv_path):
    write_csv(csv_path, [row()], [c for c in HEADER if c != "status"])
    with pytest.raises(CommandError, match="missing required column.*status"):
        run(csv_path)


def test_missing_file_is_an_error(tmp_path, monkeypatch):
    with pytest.raises(CommandError, match="not found"):
        run(tmp_path / "nope.csv")
    monkeypatch.setenv("SOURCES_CSV", str(tmp_path / "also-missing.csv"))
    with pytest.raises(CommandError, match="also-missing.csv"):
        call_command("load_sources", stdout=io.StringIO())


def test_sources_csv_env_sets_the_default_path(csv_path, monkeypatch):
    write_csv(csv_path, [row()])
    monkeypatch.setenv("SOURCES_CSV", str(csv_path))
    call_command("load_sources", stdout=io.StringIO())
    assert Document.objects.filter(pk="CEN-TEST-ACT").exists()


def test_samples_and_unrelated_rows_are_untouched(csv_path):
    call_command("load_sample_documents")
    samples = {d.pk: d.updated_at for d in Document.objects.all()}
    Document.objects.create(
        id="admin-added",
        title="Added in the admin",
        publisher="Admin",
        doc_type="circular",
        language="en",
        published_date=date(2024, 1, 1),
        version="1",
    )
    write_csv(csv_path, [row()])
    out = run(csv_path)

    assert f"left untouched: {len(samples) + 1} ({len(samples)} samples)" in out
    for pk, updated_at in samples.items():
        assert Document.objects.get(pk=pk).updated_at == updated_at
    assert Document.objects.get(pk="admin-added").title == "Added in the admin"


@pytest.mark.skipif(not REAL_CSV.is_file(), reason="data/sources.csv is not in this checkout")
def test_real_sources_csv_loads_without_crashing():
    out = run(REAL_CSV)
    summary = out.splitlines()[0]
    counts = dict(
        (name, int(num))
        for part in summary.split("-> ")[1].split(", ")
        for name, num in [part.split(" ")]
    )
    assert counts["created"] + counts["updated"] + counts["skipped"] == 49

    with REAL_CSV.open(encoding="utf-8-sig", newline="") as handle:
        notes = [r["notes"] for r in csv.DictReader(handle) if r.get("notes")]
    assert notes and not any(note in out for note in notes)
