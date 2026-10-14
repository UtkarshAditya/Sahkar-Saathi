"""One error shape for the whole API: ``{"code": "...", "message": "..."}``."""

import logging

from django.http import Http404
from ninja import NinjaAPI, Schema
from ninja.errors import AuthenticationError, HttpError, Throttled, ValidationError

from services.types import ProviderError, ServiceError, ServiceNotReady

logger = logging.getLogger("sahkar.api")


class ErrorOut(Schema):
    code: str
    message: str


class ApiError(HttpError):
    """Raise from a handler to return a specific code and status."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code, message)
        self.code = code


def _describe(errors: list[dict]) -> str:
    if not errors:
        return "Invalid request."
    first = errors[0]
    # Drop Ninja's internal location parts ("body", "payload", "file", "form").
    hidden = {"body", "payload", "file", "form", "query"}
    where = ".".join(str(part) for part in first.get("loc", []) if part not in hidden)
    message = first.get("msg", "Invalid value.").removeprefix("Value error, ")
    return f"{where}: {message}" if where else message


def register_error_handlers(api: NinjaAPI) -> None:
    def respond(request, status: int, code: str, message: str):
        return api.create_response(request, {"code": code, "message": message}, status=status)

    @api.exception_handler(ValidationError)
    def on_validation_error(request, exc: ValidationError):
        return respond(request, 422, "validation_error", _describe(exc.errors))

    @api.exception_handler(ApiError)
    def on_api_error(request, exc: ApiError):
        return respond(request, exc.status_code, exc.code, exc.message)

    @api.exception_handler(Throttled)
    def on_throttled(request, exc: Throttled):
        response = respond(request, 429, "rate_limited", "Too many requests. Please wait a moment.")
        if exc.wait:
            response["Retry-After"] = str(int(exc.wait) + 1)
        return response

    @api.exception_handler(AuthenticationError)
    def on_not_authenticated(request, exc: AuthenticationError):
        return respond(request, 401, "not_authenticated", "Log in as staff at /admin/ first.")

    @api.exception_handler(HttpError)
    def on_http_error(request, exc: HttpError):
        return respond(request, exc.status_code, f"http_{exc.status_code}", exc.message)

    @api.exception_handler(Http404)
    def on_not_found(request, exc: Http404):
        return respond(request, 404, "not_found", "Not found.")

    @api.exception_handler(ServiceNotReady)
    def on_not_ready(request, exc: ServiceNotReady):
        return respond(request, 503, exc.code, exc.message)

    @api.exception_handler(ProviderError)
    def on_provider_error(request, exc: ProviderError):
        logger.warning("provider error: %s", exc.message)
        return respond(request, 502, exc.code, "An upstream service failed. Please try again.")

    @api.exception_handler(ServiceError)
    def on_service_error(request, exc: ServiceError):
        logger.warning("service error %s: %s", exc.code, exc.message)
        return respond(request, 500, exc.code, exc.message)

    @api.exception_handler(Exception)
    def on_unexpected(request, exc: Exception):
        logger.exception("unhandled error on %s", request.path)
        return respond(request, 500, "internal_error", "Something went wrong on our side.")
