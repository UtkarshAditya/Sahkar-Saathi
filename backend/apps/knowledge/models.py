"""The knowledge base (architecture doc, Core data). Owned by member B; models by member A.

Text and metadata live here in PostgreSQL; vectors live in Qdrant, linked by
``Chunk.vector_id``. Retire an outdated document by setting ``status`` to retired; never
delete it, so old citations stay explainable.
"""

from django.db import models


class Document(models.Model):
    class DocType(models.TextChoices):
        ACT = "act", "Act"
        RULES = "rules", "Rules"
        MODEL_BYLAWS = "model-bylaws", "Model by-laws"
        CIRCULAR = "circular", "Circular"
        SCHEME_GUIDELINE = "scheme-guideline", "Scheme guideline"

    class Status(models.TextChoices):
        ACTIVE = "active"
        RETIRED = "retired"

    # A readable, stable id ("doc-tn-act"). Citations and "Ask about this document" use it.
    id = models.SlugField(primary_key=True, max_length=64)
    title = models.CharField(max_length=300)
    publisher = models.CharField(max_length=200)
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    state = models.CharField(
        max_length=8, default="central", help_text='A state code, or "central".'
    )
    language = models.CharField(max_length=8)
    published_date = models.DateField(
        null=True, blank=True, help_text="Empty when the source states no date."
    )
    version = models.CharField(max_length=50)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    source_url = models.URLField(
        max_length=500, blank=True, help_text="Official link. Leave empty until verified."
    )
    is_sample = models.BooleanField(
        default=False, help_text="Placeholder metadata for the demo; replace before evaluation."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "title"]
        indexes = [models.Index(fields=["state", "language", "doc_type", "status"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.version})"


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    text = models.TextField()
    page = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=300, blank=True)
    # Copied from the document so retrieval can filter without a join.
    state = models.CharField(max_length=8)
    language = models.CharField(max_length=8)
    vector_id = models.CharField(max_length=64, unique=True, help_text="Point id in Qdrant.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "page", "id"]
        indexes = [models.Index(fields=["state", "language"])]

    def __str__(self) -> str:
        page = f" p. {self.page}" if self.page else ""
        return f"{self.document_id}{page}: {self.text[:60]}"
