from django.contrib import admin

from .models import Citation, Conversation, Message


class CitationInline(admin.TabularInline):
    model = Citation
    extra = 0
    can_delete = False
    readonly_fields = ["rank", "document_title", "page", "score", "chunk_id", "document_id"]
    fields = readonly_fields


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ["created_at", "status", "language", "state", "top_score", "latency_ms"]
    readonly_fields = fields


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "last_activity_at", "message_count"]
    readonly_fields = ["id", "created_at", "last_activity_at"]
    inlines = [MessageInline]

    @admin.display(description="Messages")
    def message_count(self, obj: Conversation) -> int:
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Read-only: messages are evidence for evaluation, not something staff edit."""

    list_display = [
        "created_at",
        "status",
        "needs_state",
        "language",
        "state",
        "top_score",
        "latency_ms",
        "model_name",
        "is_demo",
    ]
    list_filter = ["status", "language", "state", "is_demo", "needs_state"]
    search_fields = ["question_text", "answer_text"]
    date_hierarchy = "created_at"
    inlines = [CitationInline]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False
