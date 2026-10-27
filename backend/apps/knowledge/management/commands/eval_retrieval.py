"""Measure retrieval on a question set and suggest a SCORE_THRESHOLD from the data.

    python manage.py eval_retrieval [--questions PATH] [--top-k N]

Reads data/eval/retrieval_questions.json (format: data/eval/README.md): a list of
``{"id", "question", "state", "in_scope", "expect_doc_ids"}``. Each question goes through
``get_retriever()``, so it measures whatever USE_STUB_RETRIEVER selects (with the stub it
only exercises the tool). Prints the top score and top document per question, the hit rate
(in-scope questions that list expect_doc_ids), and a threshold between the in-scope and
out-of-scope top scores. Read-only: it never writes to the database.
"""

import asyncio
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.services import get_retriever

MIN_GROUP_SIZE = 5
QUESTIONS_FILE = Path("data") / "eval" / "retrieval_questions.json"


def percentile(values: list[float], q: float) -> float:
    """The q-th percentile (0-100) by linear interpolation. ``values`` must not be empty."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def default_questions_path() -> Path:
    base = Path(settings.BASE_DIR)
    candidates = [base / QUESTIONS_FILE, base.parent / QUESTIONS_FILE]
    return next((path for path in candidates if path.is_file()), candidates[0])


def load_questions(path: Path) -> list[dict]:
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
    return data


class Command(BaseCommand):
    help = "Run the retrieval question set and suggest a SCORE_THRESHOLD."

    def add_arguments(self, parser):
        parser.add_argument("--questions", help="JSON question file (default: data/eval/...).")
        parser.add_argument(
            "--top-k", type=int, help="Passages to retrieve per question (default: TOP_K)."
        )

    def handle(self, *args, **options):
        path = Path(options["questions"]) if options["questions"] else default_questions_path()
        top_k = options["top_k"] or settings.TOP_K
        questions = load_questions(path)

        if settings.USE_STUB_RETRIEVER:
            self.stdout.write(
                self.style.WARNING(
                    "NOTE: USE_STUB_RETRIEVER is on, so these are the stub's canned scores, "
                    "not the real retriever's. Do not use the threshold below."
                )
            )
        self.stdout.write(f"{len(questions)} questions from {path}, top {top_k} passages each\n")

        results = self._search_all(questions, top_k)

        self.stdout.write(f"{'id':<34} {'scope':<5} {'top score':>9}  {'top document':<34} hit")
        in_scores: list[float] = []
        out_scores: list[float] = []
        hits = evaluated = 0
        for question, passages in results:
            top = max((p.score for p in passages), default=None)
            score = top if top is not None else 0.0
            (in_scores if question["in_scope"] else out_scores).append(score)

            expected = question.get("expect_doc_ids") or []
            verdict = "-"
            if question["in_scope"] and expected:
                evaluated += 1
                found = any(p.document_id in expected for p in passages)
                hits += found
                verdict = "hit" if found else "MISS"
            top_doc = max(passages, key=lambda p: p.score).document_id if passages else "-"
            self.stdout.write(
                f"{question['id']:<34} {'in' if question['in_scope'] else 'out':<5} "
                f"{'-' if top is None else f'{top:.3f}':>9}  {top_doc[:34]:<34} {verdict}"
            )

        self.stdout.write("")
        self._summary(in_scores, out_scores, hits, evaluated, top_k)

    def _search_all(self, questions: list[dict], top_k: int) -> list[tuple[dict, list]]:
        retriever = get_retriever()

        async def run():
            found = []
            for question in questions:
                try:
                    passages = await retriever.search(
                        question["question"],
                        state=question.get("state"),
                        language="en",
                        top_k=top_k,
                    )
                except Exception as exc:  # service not ready, Qdrant down, model missing
                    message = getattr(exc, "message", str(exc))
                    raise CommandError(
                        f"The retriever failed on {question['id']!r} "
                        f"({exc.__class__.__name__}): {message}"
                    ) from exc
                found.append((question, passages))
            return found

        return asyncio.run(run())

    def _summary(self, in_scores, out_scores, hits, evaluated, top_k):
        write = self.stdout.write
        if evaluated:
            write(f"Hit rate (expected document in the top {top_k}): {hits}/{evaluated}")
        else:
            write("Hit rate: n/a (no in-scope question lists expect_doc_ids yet)")
        for label, scores in (("In-scope", in_scores), ("Out-of-scope", out_scores)):
            if scores:
                write(
                    f"{label} top scores ({len(scores)}): mean "
                    f"{sum(scores) / len(scores):.3f}, min {min(scores):.3f}, "
                    f"max {max(scores):.3f}"
                )
            else:
                write(f"{label} top scores: no questions")

        current = settings.SCORE_THRESHOLD
        if in_scores:
            kept = sum(s >= current for s in in_scores)
            write(
                f"At the current SCORE_THRESHOLD={current}: {kept}/{len(in_scores)} in-scope pass"
            )
        if out_scores:
            blocked = sum(s < current for s in out_scores)
            write(
                f"At the current SCORE_THRESHOLD={current}: {blocked}/{len(out_scores)} out blocked"
            )

        if not (in_scores and out_scores):
            write(self.style.WARNING("\nNo SUGGESTED SCORE_THRESHOLD: both groups are needed."))
            return
        low_in = percentile(in_scores, 10)
        high_out = percentile(out_scores, 90)
        suggested = (low_in + high_out) / 2
        write(
            f"\n10th percentile of in-scope top scores:     {low_in:.3f}\n"
            f"90th percentile of out-of-scope top scores: {high_out:.3f}"
        )
        write(self.style.SUCCESS(f"SUGGESTED SCORE_THRESHOLD={suggested:.2f}"))
        if low_in <= high_out:
            write(
                self.style.WARNING(
                    "WARNING: the score ranges overlap, so no threshold separates in-scope from "
                    "out-of-scope questions cleanly. Do not trust the suggestion: improve "
                    "retrieval or the question set first."
                )
            )
        for label, scores in (("in-scope", in_scores), ("out-of-scope", out_scores)):
            if len(scores) < MIN_GROUP_SIZE:
                write(
                    self.style.WARNING(
                        f"WARNING: only {len(scores)} {label} questions (need at least "
                        f"{MIN_GROUP_SIZE}). The suggestion is not reliable yet."
                    )
                )
