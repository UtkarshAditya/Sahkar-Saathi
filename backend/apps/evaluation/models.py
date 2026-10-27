"""Evaluation data (architecture doc, Core data): the test questions, each run of them, and
the result for each question in a run. Written by the eval tooling (``eval_retrieval
--record``) and by staff in the admin site; read by ``GET /eval/latest``.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

UNIT = [MinValueValidator(0.0), MaxValueValidator(1.0)]


class TestQuestion(models.Model):
    """One evaluation question, loaded from data/eval/retrieval_questions.json."""

    __test__ = False  # not a pytest class, despite the name

    id = models.SlugField(primary_key=True, max_length=64)
    question = models.TextField()
    language = models.CharField(max_length=8, default="en")
    state = models.CharField(max_length=8, blank=True, help_text="A state code; empty = central.")
    in_scope = models.BooleanField(help_text="False if the assistant should decline it.")
    expect_doc_ids = models.JSONField(
        default=list, blank=True, help_text="Document ids that should be retrieved."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.id


class EvalRun(models.Model):
    """One run of the test questions with one configuration.

    A metric is null when the run did not measure it. Retrieval tooling measures the hit
    rate and the correct-refusal rate; faithfulness needs a person to check answers against
    their cited passages, and is entered in the admin site.
    """

    run_at = models.DateTimeField(default=timezone.now)
    label = models.CharField(max_length=200)
    embedding_model = models.CharField(max_length=200)
    llm = models.CharField(max_length=200, default="n/a (retrieval only)")
    top_k = models.PositiveSmallIntegerField()
    threshold = models.FloatField(help_text="SCORE_THRESHOLD in force for the run.")
    prompt_version = models.CharField(max_length=50, default="n/a (retrieval only)")
    hit_rate = models.FloatField(null=True, blank=True, validators=UNIT)
    faithfulness = models.FloatField(null=True, blank=True, validators=UNIT)
    correct_refusal = models.FloatField(null=True, blank=True, validators=UNIT)
    question_count = models.PositiveIntegerField()
    is_sample = models.BooleanField(
        default=False,
        help_text="Measured on a stub service: never shown as a real result.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["run_at", "id"]

    def __str__(self) -> str:
        return f"run-{self.pk}: {self.label}"

    @property
    def is_complete(self) -> bool:
        """The dashboard contract needs all three metrics."""
        return None not in (self.hit_rate, self.faithfulness, self.correct_refusal)


class EvalResult(models.Model):
    """What happened to one question in one run."""

    class Failure(models.TextChoices):
        RETRIEVAL_MISS = "retrieval-miss", "Expected document not retrieved"
        UNFAITHFUL = "unfaithful", "Answer not supported by its passage"
        SHOULD_DECLINE = "should-decline", "Out-of-scope question was not declined"
        WRONG_STATE = "wrong-state", "Answered from the wrong state's documents"

    run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name="results")
    question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE, related_name="results")
    top_score = models.FloatField(null=True, blank=True)
    top_document_id = models.CharField(max_length=64, blank=True)
    hit = models.BooleanField(
        null=True, blank=True, help_text="Expected document retrieved; null if none was expected."
    )
    failure = models.CharField(max_length=20, choices=Failure.choices, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["run", "question"]
        constraints = [
            models.UniqueConstraint(fields=["run", "question"], name="unique_result_per_question")
        ]

    def __str__(self) -> str:
        return f"run-{self.run_id} {self.question_id}: {self.failure or 'ok'}"
