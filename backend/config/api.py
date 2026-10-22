"""The NinjaAPI instance, mounted at /api/v1/. This is the whole API contract.

Export the contract without running a server:
    python manage.py export_openapi_schema --api config.api.api --output openapi.json --indent 2
tests/test_contract.py fails if the committed openapi.json is out of date.
"""

import urllib.request
from typing import Literal

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError, connection
from ninja import NinjaAPI, Schema

from apps.chat.api import router as chat_router
from apps.evaluation.api import router as evaluation_router
from apps.feedback.api import router as feedback_router
from apps.grievance.api import router as grievance_router
from apps.knowledge.api import router as knowledge_router
from apps.lessons.api import router as lessons_router
from apps.meta.api import router as meta_router
from apps.schemes.api import router as schemes_router
from apps.speech.api import router as speech_router

from .errors import register_error_handlers

api = NinjaAPI(
    title="Sahkar Saathi API",
    version="v1",
    description=(
        "Multilingual cooperative governance and legal-information assistant "
        "(SIH 2026, problem statement 26088). Every error uses the shape "
        '`{"code": "...", "message": "..."}`. Language codes are short ISO codes '
        "(en, hi and the regional language). Public endpoints are rate-limited."
    ),
    urls_namespace="api-v1",
    # Interactive docs are public in development and staff-only everywhere else.
    docs_decorator=None if settings.DEBUG else staff_member_required,
)

register_error_handlers(api)


class HealthOut(Schema):
    status: Literal["ok", "degraded"]
    version: str
    stubs: bool
    database: Literal["ok", "unreachable"]
    vector_store: Literal["ok", "unreachable", "not_used"]


def _database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except DatabaseError:
        return False


def _vector_store_ok() -> bool:
    url = f"{settings.QDRANT_URL.rstrip('/')}/readyz"
    try:
        with urllib.request.urlopen(url, timeout=settings.HEALTH_CHECK_TIMEOUT_SECONDS) as res:
            return res.status == 200
    except OSError:
        return False


@api.get("/health", response=HealthOut, tags=["meta"], summary="Deployment check")
async def health(request):
    """Warm this up before a demo. ``degraded`` means a dependency is down."""
    db_ok = await sync_to_async(_database_ok)()
    # Only the real retriever uses Qdrant.
    if settings.USE_STUB_RETRIEVER:
        vector_store = "not_used"
    else:
        vector_store = "ok" if await sync_to_async(_vector_store_ok)() else "unreachable"
    healthy = db_ok and vector_store != "unreachable"
    return {
        "status": "ok" if healthy else "degraded",
        "version": settings.APP_VERSION,
        # True while any service is still a stub (each has its own USE_STUB_* flag).
        "stubs": any(
            (
                settings.USE_STUB_RETRIEVER,
                settings.USE_STUB_ANSWER,
                settings.USE_STUB_SPEECH,
                settings.USE_STUB_GRIEVANCE,
            )
        ),
        "database": "ok" if db_ok else "unreachable",
        "vector_store": vector_store,
    }


api.add_router("/meta", meta_router, tags=["meta"])
api.add_router("/chat", chat_router, tags=["chat"])
api.add_router("/speech", speech_router, tags=["speech"])
api.add_router("/feedback", feedback_router, tags=["feedback"])
api.add_router("/grievance", grievance_router, tags=["grievance"])
api.add_router("/schemes", schemes_router, tags=["schemes"])
api.add_router("/lessons", lessons_router, tags=["lessons"])
api.add_router("/documents", knowledge_router, tags=["documents"])
api.add_router("/eval", evaluation_router, tags=["staff"])
