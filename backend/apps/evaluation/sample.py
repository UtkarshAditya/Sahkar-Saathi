"""SAMPLE evaluation numbers that lay out the Quality dashboard. They are NOT real results.

Replaced in Sprint 2 by TestQuestion, EvalRun and EvalResult rows written by member B's
eval runner. Targets are the ones in the architecture document (section 5).
"""

from datetime import datetime, timedelta, timezone

from .schemas import EvalMetricOut, EvalRunConfigOut, EvalRunOut, EvalSummaryOut, FailedQuestionOut

IST = timezone(timedelta(hours=5, minutes=30))

TARGETS = {"hit_rate": 0.85, "faithfulness": 0.9, "correct_refusal": 0.9}


def _run(
    n: int,
    day: int,
    label: str,
    emb: str,
    llm: str,
    threshold: float,
    prompt: str,
    hit: float,
    faith: float,
    refusal: float,
    questions: int,
) -> EvalRunOut:
    return EvalRunOut(
        id=f"run-sample-{n}",
        run_at=datetime(2026, 10, day, 18, 0, tzinfo=IST),
        label=f"Sample run {n} · {label}",
        config=EvalRunConfigOut(
            embedding_model=emb, llm=llm, top_k=4, threshold=threshold, prompt_version=prompt
        ),
        hit_rate=hit,
        faithfulness=faith,
        correct_refusal=refusal,
        questions=questions,
    )


def sample_summary() -> EvalSummaryOut:
    runs = [
        _run(1, 17, "pilot", "multilingual-e5-small", "model-a", 0.5, "v1", 0.62, 0.7, 0.55, 40),
        _run(
            2, 24, "full corpus", "multilingual-e5-base", "model-a", 0.55, "v2", 0.78, 0.84, 0.8, 80
        ),
        _run(3, 27, "tuned", "bge-m3", "model-b", 0.6, "v3", 0.86, 0.88, 0.92, 80),
    ]
    latest = runs[-1]
    return EvalSummaryOut(
        latest=latest,
        runs=runs,
        is_sample=True,
        metrics=[
            EvalMetricOut(
                key="hit_rate",
                label="Retrieval hit rate",
                value=latest.hit_rate,
                target=TARGETS["hit_rate"],
                description="Correct passage in the top 4 results, over 80 questions.",
            ),
            EvalMetricOut(
                key="faithfulness",
                label="Answer faithfulness",
                value=latest.faithfulness,
                target=TARGETS["faithfulness"],
                description="Every claim supported by its cited passage (30 answers checked).",
            ),
            EvalMetricOut(
                key="correct_refusal",
                label="Correct refusal",
                value=latest.correct_refusal,
                target=TARGETS["correct_refusal"],
                description="Declines and redirects on 20 out-of-scope questions.",
            ),
        ],
        failed_questions=[
            FailedQuestionOut(
                id="fq-1",
                question="Sample: What is the quorum for a general body meeting?",
                language="hi",
                failure="retrieval-miss",
                note="Correct by-law section ranked 6th.",
            ),
            FailedQuestionOut(
                id="fq-2",
                question="Sample: Can a defaulting member contest the board election?",
                language="en",
                failure="wrong-state",
                note="Answered from central Act; state not asked.",
            ),
            FailedQuestionOut(
                id="fq-3",
                question="Sample: How much premium do I pay for cotton?",
                language="ta",
                failure="unfaithful",
                note="Number in answer not present in cited passage.",
            ),
            FailedQuestionOut(
                id="fq-4",
                question="Sample: Which lawyer should I hire for my case?",
                language="en",
                failure="should-decline",
                note="Gave general advice instead of declining.",
            ),
        ],
    )
