"""The Quality dashboard summary built from real EvalRun rows (GET /eval/latest).

Only runs the contract can express are served: not a sample, and all three metrics set.
A run that lacks faithfulness (nobody has checked answers by hand yet) is stored but waits
in the admin site; the endpoint falls back to the sample data until a complete run exists.
"""

from .models import EvalResult, EvalRun
from .sample import TARGETS
from .schemas import EvalMetricOut, EvalRunConfigOut, EvalRunOut, EvalSummaryOut, FailedQuestionOut

MAX_RUNS = 10


def run_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=f"run-{run.pk}",
        run_at=run.run_at,
        label=run.label,
        config=EvalRunConfigOut(
            embedding_model=run.embedding_model,
            llm=run.llm,
            top_k=run.top_k,
            threshold=run.threshold,
            prompt_version=run.prompt_version,
        ),
        hit_rate=run.hit_rate,
        faithfulness=run.faithfulness,
        correct_refusal=run.correct_refusal,
        questions=run.question_count,
    )


def real_summary() -> EvalSummaryOut | None:
    """The summary of the latest complete, non-sample run, or None if there is none."""
    complete = EvalRun.objects.filter(
        is_sample=False,
        hit_rate__isnull=False,
        faithfulness__isnull=False,
        correct_refusal__isnull=False,
    )
    recent = list(complete.order_by("-run_at", "-id")[:MAX_RUNS])
    if not recent:
        return None
    latest = recent[0]
    results = EvalResult.objects.filter(run=latest).select_related("question")
    with_expected = results.filter(hit__isnull=False).count()
    out_of_scope = results.filter(question__in_scope=False).count()

    metrics = [
        EvalMetricOut(
            key="hit_rate",
            label="Retrieval hit rate",
            value=latest.hit_rate,
            target=TARGETS["hit_rate"],
            description=(
                f"Correct passage in the top {latest.top_k} results, "
                f"over {with_expected} questions."
            ),
        ),
        EvalMetricOut(
            key="faithfulness",
            label="Answer faithfulness",
            value=latest.faithfulness,
            target=TARGETS["faithfulness"],
            description="Every claim supported by its cited passage, checked by hand.",
        ),
        EvalMetricOut(
            key="correct_refusal",
            label="Correct refusal",
            value=latest.correct_refusal,
            target=TARGETS["correct_refusal"],
            description=(
                f"Declines on {out_of_scope} out-of-scope questions "
                "(best retrieval score below the threshold)."
            ),
        ),
    ]
    failed = [
        FailedQuestionOut(
            id=r.question_id,
            question=r.question.question,
            language=r.question.language,
            failure=r.failure,
            note=r.note,
        )
        for r in results.exclude(failure="")
    ]
    return EvalSummaryOut(
        latest=run_out(latest),
        metrics=metrics,
        runs=[run_out(r) for r in reversed(recent)],
        failed_questions=failed,
        is_sample=False,
    )
