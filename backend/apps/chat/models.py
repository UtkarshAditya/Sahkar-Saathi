"""Anonymous conversations, kept for evaluation and debugging (architecture doc, Core data).

No user account, name or contact detail is ever linked. Question and answer text is
stored only when STORE_MESSAGES is on, and only after ``services.privacy.scrub_pii``.
"""

import uuid

from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]

    def __str__(self) -> str:
        return f"Conversation {self.id.hex[:8]}"


class Message(models.Model):
    """One question and the answer to it."""

    class Status(models.TextChoices):
        ANSWERED = "answered"
        PARTIAL = "partial"
        DECLINED = "declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Text: empty when STORE_MESSAGES is off.
    question_text = models.TextField(blank=True)
    answer_text = models.TextField(blank=True)

    # Request context.
    language = models.CharField(max_length=8)
    state = models.CharField(max_length=8, blank=True)
    document_id = models.CharField(
        max_length=64, blank=True, help_text="Set when the question was limited to one document."
    )

    # Outcome, always stored.
    status = models.CharField(max_length=10, choices=Status.choices)
    needs_state = models.BooleanField(default=False)
    top_score = models.FloatField(null=True, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField()
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.status} · {self.language} · {self.created_at:%Y-%m-%d %H:%M}"


class Citation(models.Model):
    """A passage that supported an answer. A snapshot, so it survives re-ingestion.

    ``chunk_id`` and ``document_id`` refer to member B's Chunk and Document records; they
    become foreign keys once the knowledge app has models.
    """

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="citations")
    rank = models.PositiveSmallIntegerField()
    chunk_id = models.CharField(max_length=100)
    document_id = models.CharField(max_length=64)
    document_title = models.CharField(max_length=300)
    page = models.PositiveIntegerField(null=True, blank=True)
    score = models.FloatField()

    class Meta:
        ordering = ["message", "rank"]
        constraints = [
            models.UniqueConstraint(fields=["message", "rank"], name="unique_citation_rank")
        ]

    def __str__(self) -> str:
        page = f", p. {self.page}" if self.page else ""
        return f"[{self.rank}] {self.document_title}{page}"
