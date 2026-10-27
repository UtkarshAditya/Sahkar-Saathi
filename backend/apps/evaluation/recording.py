"""Save a retrieval evaluation as an EvalRun with one EvalResult per question.

Only what the retrieval tooling measured is stored: the hit rate and the correct-refusal
rate. Faithfulness stays empty unless a person supplies it after checking answers by hand.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from .models import EvalResult, EvalRun, TestQuestion
from .questions import sync_test_questions


@dataclass
class Outcome:
    """What retrieval returned for one question."""

    question: dict  # an item of the question file
    top_score: float | None
    top_document_id: str
    hit: bool | None  # None when no document was expected


def refused(outcome: Outcome, threshold: float) -> bool:
    """The answer service declines when the best score is below the threshold (or no hit)."""
    return outcome.top_score is None or outcome.top_score < threshold


def record_run(
    outcomes: list[Outcome],
    *,
    label: str,
    embedding_model: str,
    top_k: int,
    threshold: float,
    llm: str | None = None,
    prompt_version: str | None = None,
    faithfulness: float | None = None,
    is_sample: bool = False,
    notes: str = "",
    run_at: datetime | None = None,
) -> EvalRun:
    in_scope = [o for o in outcomes if o.question["in_scope"]]
    out_of_scope = [o for o in outcomes if not o.question["in_scope"]]
    expected = [o for o in in_scope if o.hit is not None]

    hit_rate = sum(bool(o.hit) for o in expected) / len(expected) if expected else None
    correct_refusal = (
        sum(refused(o, threshold) for o in out_of_scope) / len(out_of_scope)
        if out_of_scope
        else None
    )

    with transaction.atomic():
        sync_test_questions([o.question for o in outcomes])
        extra = {k: v for k, v in {"llm": llm, "prompt_version": prompt_version}.items() if v}
        if run_at:
            extra["run_at"] = run_at
        run = EvalRun.objects.create(
            label=label,
            embedding_model=embedding_model,
            top_k=top_k,
            threshold=threshold,
            hit_rate=hit_rate,
            faithfulness=faithfulness,
            correct_refusal=correct_refusal,
            question_count=len(outcomes),
            is_sample=is_sample,
            notes=notes,
            **extra,
        )
        questions = TestQuestion.objects.in_bulk([o.question["id"] for o in outcomes])
        EvalResult.objects.bulk_create(
            _result(run, questions[o.question["id"]], o, threshold) for o in outcomes
        )
    return run


def _result(run: EvalRun, question: TestQuestion, outcome: Outcome, threshold: float):
    failure, note = "", ""
    if question.in_scope and outcome.hit is False:
        failure = EvalResult.Failure.RETRIEVAL_MISS
        note = f"Expected {', '.join(question.expect_doc_ids)}; best match was " + (
            outcome.top_document_id or "nothing"
        )
    elif not question.in_scope and not refused(outcome, threshold):
        failure = EvalResult.Failure.SHOULD_DECLINE
        note = f"Best score {outcome.top_score:.3f} is not below the threshold {threshold}."
    return EvalResult(
        run=run,
        question=question,
        top_score=outcome.top_score,
        top_document_id=outcome.top_document_id[:64],
        hit=outcome.hit,
        failure=failure,
        note=note[:300],
    )
