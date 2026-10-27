from django.contrib import admin

from .models import EvalResult, EvalRun, TestQuestion


@admin.register(TestQuestion)
class TestQuestionAdmin(admin.ModelAdmin):
    __test__ = False

    list_display = ["id", "in_scope", "state", "language", "question_short"]
    list_filter = ["in_scope", "language", "state"]
    search_fields = ["id", "question"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Question")
    def question_short(self, obj: TestQuestion) -> str:
        return obj.question[:80]


class EvalResultInline(admin.TabularInline):
    model = EvalResult
    extra = 0
    can_delete = False
    fields = ["question", "top_score", "top_document_id", "hit", "failure", "note"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    """Enter faithfulness here after checking answers by hand: the Quality dashboard shows
    a run only when all three metrics are set and the run is not a sample."""

    list_display = [
        "__str__",
        "run_at",
        "hit_rate",
        "faithfulness",
        "correct_refusal",
        "question_count",
        "is_sample",
    ]
    list_filter = ["is_sample"]
    inlines = [EvalResultInline]


@admin.register(EvalResult)
class EvalResultAdmin(admin.ModelAdmin):
    list_display = ["run", "question", "top_score", "hit", "failure"]
    list_filter = ["failure", "hit"]
    raw_id_fields = ["run", "question"]
