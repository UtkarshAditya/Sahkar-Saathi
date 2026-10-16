"""Load document metadata from the sources inventory (``data/sources.csv``) into Document.

Metadata only: no chunking, embedding or Qdrant. The CSV is the source of truth for the
fields it carries, so a re-run overwrites them; documents that are not in the CSV (samples,
or ones added in the admin site) are never touched.

Validation is strict and follows the current model. Nothing is guessed, converted or
truncated: a row that does not fit is skipped and reported with its line number, so the
CSV owner can fix it. The one accepted alias is a doc_type label ("Act" for "act").

    python manage.py load_sources [--path PATH] [--dry-run] [--strict]
"""

import csv
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator, validate_slug
from django.db import transaction

from apps.knowledge.models import Document

REQUIRED = [
    "doc_id",
    "title",
    "publisher",
    "doc_type",
    "state",
    "language",
    "version",
    "status",
]
OPTIONAL = ["source_url", "published_date"]
# CSV column -> the model field's max length
MAX_LENGTHS = {
    "doc_id": 64,
    "title": 300,
    "publisher": 200,
    "language": 8,
    "version": 50,
    "source_url": 500,
}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DOC_TYPE_LABELS = {str(label).lower(): value for value, label in Document.DocType.choices}
# Cell values worth showing in the summary. Long text fields are reported by length only.
SHOWN_VALUES = {"doc_type", "state", "status", "published_date", "language"}


@dataclass
class Problem:
    kind: str  # groups problems in the summary, e.g. "doc_type is not a known type"
    message: str  # the per-row text
    value: str | None = None  # the offending cell, for short fields only


@dataclass
class Row:
    line: int
    doc_id: str
    values: dict = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)


def default_path() -> Path:
    env = os.environ.get("SOURCES_CSV")
    return Path(env) if env else Path(settings.BASE_DIR).parent / "data" / "sources.csv"


def show(value: str, limit: int = 40) -> str:
    """Quote a cell for the report. Display only; the stored value is never shortened."""
    return repr(value if len(value) <= limit else value[:limit] + "…")


def validate(cells: dict, has_url_column: bool) -> tuple[dict, list[Problem]]:
    problems: list[Problem] = []
    get = {col: cells.get(col) or "" for col in REQUIRED + OPTIONAL}

    for col in REQUIRED:
        if not get[col].strip():
            problems.append(Problem(f"{col} is empty", f"{col} is empty"))
    for col, limit in MAX_LENGTHS.items():
        if len(get[col]) > limit:
            problems.append(
                Problem(
                    f"{col} is longer than {limit} characters",
                    f"{col} has {len(get[col])} characters (max {limit})",
                )
            )

    doc_id = get["doc_id"]
    if doc_id.strip():
        try:
            validate_slug(doc_id)
        except ValidationError:
            problems.append(
                Problem(
                    "doc_id is not a valid slug",
                    f"doc_id {show(doc_id)} may only use letters, digits, '-' and '_'",
                )
            )

    doc_type = get["doc_type"]
    if doc_type in Document.DocType.values:
        resolved_type = doc_type
    else:
        resolved_type = DOC_TYPE_LABELS.get(doc_type.lower())
    if doc_type.strip() and resolved_type is None:
        problems.append(
            Problem(
                "doc_type is not a known type",
                f"doc_type {show(doc_type)} is not a known type",
                doc_type,
            )
        )

    status = get["status"]
    if status.strip() and status not in Document.Status.values:
        allowed = ", ".join(repr(v) for v in Document.Status.values)
        problems.append(
            Problem(
                "status is not a known status",
                f"status {show(status)} must be one of {allowed}",
                status,
            )
        )

    state = get["state"]
    if state.strip() and state != "central" and (len(state) > 8 or re.search(r"\s", state)):
        problems.append(
            Problem(
                "state is not 'central' or a short code",
                f"state {show(state)} must be 'central' or a code like 'TN'",
                state,
            )
        )

    # Empty or absent means the source states no date: stored as NULL. Anything else must
    # be a full YYYY-MM-DD date; partial dates such as "2018" are not completed.
    raw_date = get["published_date"]
    published = None
    if raw_date:
        if DATE_RE.fullmatch(raw_date):
            try:
                published = date.fromisoformat(raw_date)
            except ValueError:
                pass
        if published is None:
            problems.append(
                Problem(
                    "published_date is not YYYY-MM-DD",
                    f"published_date {show(raw_date)} is not a YYYY-MM-DD date",
                    raw_date,
                )
            )

    url = get["source_url"]
    if url:
        try:
            URLValidator()(url)
        except ValidationError:
            problems.append(Problem("source_url is not a valid URL", "source_url is not a URL"))

    values = {
        "title": get["title"],
        "publisher": get["publisher"],
        "doc_type": resolved_type,
        "state": state,
        "language": get["language"],
        "published_date": published,
        "version": get["version"],
        "status": status,
        "is_sample": False,
    }
    if has_url_column:
        values["source_url"] = url
    return values, problems


class Command(BaseCommand):
    help = "Load document metadata from data/sources.csv into the Document table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", help="CSV file (default: $SOURCES_CSV, else <repo>/data/sources.csv)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Validate and report; write nothing."
        )
        parser.add_argument(
            "--strict", action="store_true", help="Write nothing if any row is invalid."
        )

    def handle(self, *args, **options):
        path = Path(options["path"]) if options["path"] else default_path()
        if not path.is_file():
            raise CommandError(f"load_sources: CSV file not found: {path}")
        rows = self.read(path)

        # A duplicated id is ambiguous, so every copy is skipped rather than picking one.
        id_counts = Counter(row.doc_id for row in rows if row.doc_id)
        for row in rows:
            if id_counts[row.doc_id] > 1:
                row.problems.append(
                    Problem(
                        "doc_id appears more than once",
                        f"doc_id appears {id_counts[row.doc_id]} times in the file",
                    )
                )

        valid = [row for row in rows if not row.problems]
        skipped = [row for row in rows if row.problems]
        existing = Document.objects.in_bulk([row.doc_id for row in valid])

        created, updated, unchanged = [], [], []
        for row in valid:
            doc = existing.get(row.doc_id)
            if doc is None:
                created.append(row)
            elif any(getattr(doc, name) != value for name, value in row.values.items()):
                updated.append(row)
            else:
                unchanged.append(row)

        write = not options["dry_run"] and not (options["strict"] and skipped)
        if write:
            with transaction.atomic():
                for row in created:
                    Document.objects.create(id=row.doc_id, **row.values)
                for row in updated:
                    doc = existing[row.doc_id]
                    for name, value in row.values.items():
                        setattr(doc, name, value)
                    doc.save()

        self.report(rows, created, updated, unchanged, skipped, options)
        if options["strict"] and skipped:
            raise CommandError(
                f"load_sources: --strict and {len(skipped)} invalid row(s); nothing written."
            )

    def read(self, path: Path) -> list[Row]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            missing = [col for col in REQUIRED if col not in header]
            if missing:
                raise CommandError(
                    f"load_sources: {path.name} is missing required column(s): "
                    + ", ".join(missing)
                )
            has_url_column = "source_url" in header
            rows = []
            start = reader.line_num + 1
            for cells in reader:
                doc_id = cells.get("doc_id") or ""
                values, problems = validate(cells, has_url_column)
                if cells.get(None):
                    problems.append(
                        Problem("row has more cells than the header", "has extra cells")
                    )
                rows.append(Row(start, doc_id, values, problems))
                start = reader.line_num + 1
        return rows

    def report(self, rows, created, updated, unchanged, skipped, options):
        out = self.stdout
        prefix = "load_sources"
        if options["dry_run"]:
            prefix += " (dry run, nothing written)"
        elif options["strict"] and skipped:
            prefix += " (strict, nothing written)"
        summary = (
            f"{prefix}: {len(rows)} rows -> created {len(created)}, updated {len(updated)}, "
            f"unchanged {len(unchanged)}, skipped {len(skipped)}"
        )
        out.write(self.style.WARNING(summary) if skipped else self.style.SUCCESS(summary))

        for row in skipped:
            reasons = "; ".join(problem.message for problem in row.problems)
            out.write(self.style.WARNING(f"  line {row.line} {row.doc_id or '(no id)'}: {reasons}"))

        if skipped:
            by_kind: dict[str, set[int]] = defaultdict(set)
            values: dict[str, Counter] = defaultdict(Counter)
            for row in skipped:
                for problem in row.problems:
                    by_kind[problem.kind].add(row.line)
                    if problem.value is not None:
                        values[problem.kind][problem.value] += 1
            out.write("Skipped rows by reason (a row can have several):")
            for kind, lines in sorted(by_kind.items(), key=lambda item: (-len(item[1]), item[0])):
                detail = ""
                if values[kind]:
                    detail = (
                        " ("
                        + ", ".join(
                            f"{show(value)} x{count}" for value, count in values[kind].most_common()
                        )
                        + ")"
                    )
                out.write(f"  {len(lines):>3}  {kind}{detail}")

        csv_ids = {row.doc_id for row in rows}
        others = Document.objects.exclude(id__in=csv_ids)
        out.write(
            f"Documents not in the CSV, left untouched: {others.count()} "
            f"({others.filter(is_sample=True).count()} samples)"
        )
