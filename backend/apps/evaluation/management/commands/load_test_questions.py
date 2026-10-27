"""Load the evaluation questions into the TestQuestion table.

    python manage.py load_test_questions [--path PATH]

Reads data/eval/retrieval_questions.json (format: data/eval/README.md) and upserts by id, so
a re-run updates edited questions and changes nothing otherwise. Questions that are not in
the file are left alone. ``eval_retrieval --record`` does this itself; use this command to
look at or edit the questions in the admin site first.
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.evaluation.models import TestQuestion
from apps.evaluation.questions import default_questions_path, load_questions, sync_test_questions


class Command(BaseCommand):
    help = "Load data/eval/retrieval_questions.json into TestQuestion."

    def add_arguments(self, parser):
        parser.add_argument("--path", help="JSON question file (default: data/eval/...).")

    def handle(self, *args, **options):
        path = Path(options["path"]) if options["path"] else default_questions_path()
        questions = load_questions(path)
        created, updated, unchanged = sync_test_questions(questions)
        in_scope = sum(q["in_scope"] for q in questions)
        self.stdout.write(
            f"load_test_questions: {len(questions)} questions ({in_scope} in scope, "
            f"{len(questions) - in_scope} out of scope) -> created {created}, "
            f"updated {updated}, unchanged {unchanged}"
        )
        others = TestQuestion.objects.exclude(id__in=[q["id"] for q in questions]).count()
        if others:
            self.stdout.write(f"{others} other question(s) in the database were left untouched.")
