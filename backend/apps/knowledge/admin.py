from django.contrib import admin

from .models import Chunk, Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Add, update or retire documents. Retire rather than delete."""

    list_display = [
        "title",
        "doc_type",
        "state",
        "language",
        "published_date",
        "version",
        "status",
        "is_sample",
        "chunk_count",
    ]
    list_filter = ["status", "doc_type", "state", "language", "is_sample"]
    search_fields = ["id", "title", "publisher"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["retire"]

    @admin.display(description="Chunks")
    def chunk_count(self, obj: Document) -> int:
        return obj.chunks.count()

    @admin.action(description="Retire selected documents")
    def retire(self, request, queryset):
        updated = queryset.update(status=Document.Status.RETIRED)
        self.message_user(request, f"Retired {updated} document(s).")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    """Inspect chunks; the ingest command (member B) creates them."""

    list_display = ["document", "page", "section", "state", "language", "vector_id"]
    list_filter = ["state", "language", "document__doc_type"]
    search_fields = ["text", "section", "document__title"]
    raw_id_fields = ["document"]
