from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """Review queue: filter by "Not helpful" to find wrong or unclear answers."""

    list_display = ["created_at", "rating", "reason", "short_comment", "answer_link"]
    list_filter = ["rating", "reason"]
    search_fields = ["comment", "reason"]
    date_hierarchy = "created_at"
    readonly_fields = ["message", "rating", "reason", "comment", "created_at"]

    def has_add_permission(self, request) -> bool:
        return False

    @admin.display(description="Comment")
    def short_comment(self, obj: Feedback) -> str:
        return obj.comment[:80]

    @admin.display(description="Answer")
    def answer_link(self, obj: Feedback):
        if not obj.message_id:
            return "General"
        url = reverse("admin:chat_message_change", args=[obj.message_id])
        return format_html('<a href="{}">{}</a>', url, obj.message.status)
