from django.db import models

from apps.chat.models import Message


class Feedback(models.Model):
    """A rating on one answer (Ask page) or a general comment (About page).

    Comments pass through ``services.privacy.scrub_pii`` before they are saved.
    """

    class Rating(models.TextChoices):
        UP = "up", "Helpful"
        DOWN = "down", "Not helpful"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feedback",
        help_text="Empty for general feedback that is not about one answer.",
    )
    rating = models.CharField(max_length=4, choices=Rating.choices, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "feedback"

    def __str__(self) -> str:
        return f"{self.get_rating_display() or 'Comment'} · {self.created_at:%Y-%m-%d %H:%M}"
