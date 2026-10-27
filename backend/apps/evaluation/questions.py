"""The evaluation question file (data/eval/retrieval_questions.json) and TestQuestion rows.

The file format is described in data/eval/README.md. Other keys in an item (``TODO_owner``,
``source``) are notes and are ignored.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from .models import TestQuestion

QUESTIONS_FILE = Path("data") / "eval" / "retrieval_questions.json"


def default_questions_path() -> Path:
    base = Path(settings.BASE_DIR)
    candidates = [base / QUESTIONS_FILE, base.parent / QUESTIONS_FILE]
    return next((path for path in candidates if path.is_file()), candidates[0])


def load_questions(path: Path) -> list[dict]:
    """Read and validate the question file. Raises CommandError with the item at fault."""
    if not path.is_file():
        raise CommandError(f"Question file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise CommandError(f"{path.name} is not valid JSON: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise CommandError(f"{path.name} must be a non-empty JSON list of questions.")

    seen: set[str] = set()
    for index, item in enumerate(data, start=1):
        where = f"{path.name} item {index}"
        if not isinstance(item, dict):
            raise CommandError(f"{where} must be an object.")
        for key, kind in (("id", str), ("question", str), ("in_scope", bool)):
            if not isinstance(item.get(key), kind) or item.get(key) == "":
                raise CommandError(f"{where} needs {key!r} ({kind.__name__}).")
        if item["id"] in seen:
            raise CommandError(f"{where}: id {item['id']!r} appears twice.")
        seen.add(item["id"])
        if item.get("state") is not None and not isinstance(item["state"], str):
            raise CommandError(f"{where}: 'state' must be null or a state code.")
        expected = item.get("expect_doc_ids", [])
        if not isinstance(expected, list) or not all(isinstance(d, str) for d in expected):
            raise CommandError(f"{where}: 'expect_doc_ids' must be a list of document ids.")
        if len(item["id"]) > 64 or not item["id"].replace("-", "").replace("_", "").isalnum():
            raise CommandError(f"{where}: id {item['id']!r} must be a slug of at most 64 chars.")
        if len(item.get("state") or "") > 8:
            raise CommandError(f"{where}: 'state' must be a short state code.")
    return data


def sync_test_questions(questions: list[dict]) -> tuple[int, int, int]:
    """Upsert TestQuestion rows from validated question dicts. Questions that are in the
    database but not in ``questions`` are left alone. Returns (created, updated, unchanged)."""
    created = updated = unchanged = 0
    with transaction.atomic():
        existing = TestQuestion.objects.in_bulk([q["id"] for q in questions])
        for item in questions:
            values = {
                "question": item["question"],
                "state": item.get("state") or "",
                "in_scope": item["in_scope"],
                "expect_doc_ids": list(item.get("expect_doc_ids") or []),
            }
            row = existing.get(item["id"])
            if row is None:
                TestQuestion.objects.create(id=item["id"], **values)
                created += 1
            elif any(getattr(row, name) != value for name, value in values.items()):
                for name, value in values.items():
                    setattr(row, name, value)
                row.save()
                updated += 1
            else:
                unchanged += 1
    return created, updated, unchanged
