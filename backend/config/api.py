"""The NinjaAPI instance, mounted at /api/v1/.

Export the contract without running a server:
    python manage.py export_openapi_schema --api config.api.api --output openapi.json --indent 2
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI, Schema

from apps.chat.api import router as chat_router
from apps.speech.api import router as speech_router

from .errors import register_error_handlers

api = NinjaAPI(
    title="Sahkar Saathi API",
    version="v1",
    description=(
        "Multilingual cooperative governance and legal-information assistant "
        "(SIH 2026, problem statement 26088). Every error uses the shape "
        '`{"code": "...", "message": "..."}`.'
    ),
    urls_namespace="api-v1",
    # Interactive docs are public in development and staff-only everywhere else.
    docs_decorator=None if settings.DEBUG else staff_member_required,
)

register_error_handlers(api)


class HealthOut(Schema):
    status: str
    version: str
    stubs: bool


@api.get("/health", response=HealthOut, tags=["meta"], summary="Deployment check")
def health(request):
    # Database and vector-store reachability are added when those services exist.
    return {"status": "ok", "version": settings.APP_VERSION, "stubs": settings.USE_STUBS}


api.add_router("/chat", chat_router, tags=["chat"])
api.add_router("/speech", speech_router, tags=["speech"])
