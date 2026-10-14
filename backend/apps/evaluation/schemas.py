from datetime import datetime
from typing import Literal

from ninja import Field, Schema

MetricKey = Literal["hit_rate", "faithfulness", "correct_refusal"]


class EvalRunConfigOut(Schema):
    embedding_model: str
    llm: str
    top_k: int
    threshold: float
    prompt_version: str


class EvalRunOut(Schema):
    id: str
    run_at: datetime
    label: str
    config: EvalRunConfigOut
    hit_rate: float = Field(..., ge=0, le=1)
    faithfulness: float = Field(..., ge=0, le=1)
    correct_refusal: float = Field(..., ge=0, le=1)
    questions: int


class EvalMetricOut(Schema):
    key: MetricKey
    label: str
    value: float = Field(..., ge=0, le=1)
    target: float = Field(..., ge=0, le=1)
    description: str


class FailedQuestionOut(Schema):
    id: str
    question: str
    language: str
    failure: Literal["retrieval-miss", "unfaithful", "should-decline", "wrong-state"]
    note: str


class EvalSummaryOut(Schema):
    latest: EvalRunOut
    metrics: list[EvalMetricOut]
    runs: list[EvalRunOut] = Field(..., description="Oldest first.")
    failed_questions: list[FailedQuestionOut]
    is_sample: bool = Field(..., description="True until real EvalRun rows exist.")
