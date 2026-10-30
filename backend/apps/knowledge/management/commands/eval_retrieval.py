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
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.evaluation.questions import default_questions_path, load_questions
from apps.evaluation.recording import Outcome, record_run
from config.services import get_retriever

MIN_GROUP_SIZE = 5


def percentile(values: list[float], q: float) -> float:
    """The q-th percentile (0-100) by linear interpolation. ``values`` must not be empty."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


class Command(BaseCommand):
    help = "Run the retrieval question set and suggest a SCORE_THRESHOLD."

    def add_arguments(self, parser):
        parser.add_argument("--questions", help="JSON question file (default: data/eval/...).")
        parser.add_argument(
            "--top-k", type=int, help="Passages to retrieve per question (default: TOP_K)."
        )
        record = parser.add_argument_group("recording (feeds the Quality dashboard)")
        record.add_argument(
            "--record",
            action="store_true",
            help="Save the run (EvalRun and EvalResult rows) and sync the TestQuestion rows.",
        )
        record.add_argument("--label", help="Name of the run (default: 'Retrieval run <date>').")
        record.add_argument("--llm", help="LLM name, if answers were also produced.")
        record.add_argument("--prompt-version", help="Prompt version, if answers were produced.")
        record.add_argument(
            "--faithfulness",
            type=float,
            help="0 to 1, from checking answers against their passages by hand. Without it the "
            "run waits in the admin site and the dashboard keeps the previous run.",
        )
        record.add_argument(
            "--allow-stub",
            action="store_true",
            help="Record a run measured on the stub retriever. It is marked as a sample and "
            "never shown as a real result.",
        )

    def handle(self, *args, **options):
        path = Path(options["questions"]) if options["questions"] else default_questions_path()
        top_k = options["top_k"] or settings.TOP_K
        questions = load_questions(path)
        record = options["record"]
        if record:
            self._check_record_options(options)
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
        outcomes: list[Outcome] = []
        for question, passages in results:
            top = max((p.score for p in passages), default=None)
            score = top if top is not None else 0.0
            (in_scores if question["in_scope"] else out_scores).append(score)

            expected = question.get("expect_doc_ids") or []
            verdict = "-"
            found = None
            if question["in_scope"] and expected:
                evaluated += 1
                found = any(p.document_id in expected for p in passages)
                hits += found
                verdict = "hit" if found else "MISS"
            top_doc = max(passages, key=lambda p: p.score).document_id if passages else "-"
            outcomes.append(Outcome(question, top, top_doc if passages else "", found))
            self.stdout.write(
                f"{question['id']:<34} {'in' if question['in_scope'] else 'out':<5} "
                f"{'-' if top is None else f'{top:.3f}':>9}  {top_doc[:34]:<34} {verdict}"
            )

        self.stdout.write("")
        self._summary(in_scores, out_scores, hits, evaluated, top_k)

        # Per-language report for en, hi, ta
        by_lang: dict[str, dict] = {}
        for question, passages in results:
            lang = question.get("language") or "en"
            if lang not in by_lang:
                by_lang[lang] = {
                    "in_scores": [],
                    "out_scores": [],
                    "hits": 0,
                    "evaluated": 0,
                }
            top = max((p.score for p in passages), default=None)
            score = top if top is not None else 0.0
            (
                by_lang[lang]["in_scores"]
                if question["in_scope"]
                else by_lang[lang]["out_scores"]
            ).append(score)
            expected = question.get("expect_doc_ids") or []
            if question["in_scope"] and expected:
                by_lang[lang]["evaluated"] += 1
                if any(p.document_id in expected for p in passages):
                    by_lang[lang]["hits"] += 1

        for lang in ("en", "hi", "ta"):
            if lang not in by_lang:
                continue
            data = by_lang[lang]
            self.stdout.write(f"\n--- Language: {lang} ---")
            self._summary(
                data["in_scores"],
                data["out_scores"],
                data["hits"],
                data["evaluated"],
                top_k,
                lang=lang,
            )

        if record:
            self._record(outcomes, options, top_k)

    def _check_record_options(self, options) -> None:
        if settings.USE_STUB_RETRIEVER and not options["allow_stub"]:
            raise CommandError(
                "Refusing to record: USE_STUB_RETRIEVER is on, so the scores are the stub's. "
                "Switch the real retriever on, or pass --allow-stub to record a sample run."
            )
        faithfulness = options["faithfulness"]
        if faithfulness is not None and not 0 <= faithfulness <= 1:
            raise CommandError("--faithfulness must be between 0 and 1.")

    def _record(self, outcomes: list[Outcome], options, top_k: int) -> None:
        is_sample = bool(settings.USE_STUB_RETRIEVER)
        run = record_run(
            outcomes,
            label=options["label"] or f"Retrieval run {timezone.now():%Y-%m-%d %H:%M}",
            embedding_model=settings.EMBEDDING_MODEL,
            top_k=top_k,
            threshold=settings.SCORE_THRESHOLD,
            llm=options["llm"],
            prompt_version=options["prompt_version"],
            faithfulness=options["faithfulness"],
            is_sample=is_sample,
            notes="Measured on the stub retriever." if is_sample else "",
        )
        measured = {
            "hit rate": run.hit_rate,
            "correct refusal": run.correct_refusal,
            "faithfulness": run.faithfulness,
        }
        text = ", ".join(
            f"{name} {'not measured' if value is None else f'{value:.2f}'}"
            for name, value in measured.items()
        )
        self.stdout.write(self.style.SUCCESS(f"\nRecorded run-{run.pk}: {text}."))
        if is_sample:
            self.stdout.write(self.style.WARNING("It is marked as a sample (stub retriever)."))
        elif not run.is_complete:
            self.stdout.write(
                self.style.WARNING(
                    "The Quality dashboard shows a run only when all three metrics are set. "
                    "Enter the missing ones in the admin site (Eval runs), or re-run with "
                    "--faithfulness once answers have been checked by hand."
                )
            )
        else:
            self.stdout.write("It is now the latest run on the Quality dashboard.")

    def _search_all(self, questions: list[dict], top_k: int) -> list[tuple[dict, list]]:
        retriever = get_retriever()

        async def run():
            found = []
            for question in questions:
                try:
                    passages = await retriever.search(
                        question["question"],
                        state=question.get("state"),
                        language=question.get("language", "en"),
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

    def _summary(self, in_scores, out_scores, hits, evaluated, top_k, lang: str | None = None):
        write = self.stdout.write
        title_suffix = f" ({lang})" if lang else ""
        if evaluated:
            write(
                f"Hit rate (expected document in the top {top_k}){title_suffix}: {hits}/{evaluated}"
            )
        else:
            write(f"Hit rate{title_suffix}: n/a (no in-scope question lists expect_doc_ids yet)")
        for label, scores in (("In-scope", in_scores), ("Out-of-scope", out_scores)):
            if scores:
                write(
                    f"{label} top scores ({len(scores)}){title_suffix}: mean "
                    f"{sum(scores) / len(scores):.3f}, min {min(scores):.3f}, "
                    f"max {max(scores):.3f}"
                )
            else:
                write(f"{label} top scores{title_suffix}: no questions")

        current = (
            settings.SCORE_THRESHOLD_BY_LANG.get(lang, settings.SCORE_THRESHOLD)
            if lang
            else settings.SCORE_THRESHOLD
        )
        if in_scores:
            kept = sum(s >= current for s in in_scores)
            write(
                f"At the current SCORE_THRESHOLD{title_suffix}={current}: "
                f"{kept}/{len(in_scores)} in-scope pass"
            )
        if out_scores:
            blocked = sum(s < current for s in out_scores)
            write(
                f"At the current SCORE_THRESHOLD{title_suffix}={current}: "
                f"{blocked}/{len(out_scores)} out blocked"
            )

        if not (in_scores and out_scores):
            write(
                self.style.WARNING(
                    f"\nNo SUGGESTED SCORE_THRESHOLD{title_suffix}: both groups are needed."
                )
            )
            for label, scores in (("in-scope", in_scores), ("out-of-scope", out_scores)):
                if len(scores) < MIN_GROUP_SIZE:
                    write(
                        self.style.WARNING(
                            f"WARNING: only {len(scores)} {label} questions{title_suffix} "
                            f"(need at least {MIN_GROUP_SIZE}). The suggestion is not reliable yet."
                        )
                    )
            return
        low_in = percentile(in_scores, 10)
        high_out = percentile(out_scores, 90)
        if low_in <= high_out:
            suggested = max((low_in + high_out) / 2, high_out)
        else:
            suggested = (low_in + high_out) / 2
        write(
            f"\n10th percentile of in-scope top scores{title_suffix}:     {low_in:.3f}\n"
            f"90th percentile of out-of-scope top scores{title_suffix}: {high_out:.3f}"
        )
        write(self.style.SUCCESS(f"SUGGESTED SCORE_THRESHOLD{title_suffix}={suggested:.2f}"))
        if low_in <= high_out:
            write(
                self.style.WARNING(
                    f"WARNING: the score ranges overlap{title_suffix}, so no threshold "
                    "separates in-scope from out-of-scope questions cleanly. Do not trust the "
                    "suggestion: improve retrieval or the question set first."
                )
            )
        for label, scores in (("in-scope", in_scores), ("out-of-scope", out_scores)):
            if len(scores) < MIN_GROUP_SIZE:
                write(
                    self.style.WARNING(
                        f"WARNING: only {len(scores)} {label} questions{title_suffix} "
                        f"(need at least {MIN_GROUP_SIZE}). The suggestion is not reliable yet."
                    )
                )
