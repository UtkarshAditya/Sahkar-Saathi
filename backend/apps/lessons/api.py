from ninja import Query, Router

from apps.chat.schemas import validate_language
from config.errors import ApiError, ErrorOut

from .content import load_lessons
from .schemas import LessonsOut

router = Router()


@router.get("", response={200: LessonsOut, 422: ErrorOut}, summary="Financial-literacy lessons")
def lessons(request, language: str = Query("en")):
    """Short lessons and the optional three-question quiz. Falls back to English when the
    requested language has no translation yet; ``language`` in the response says which."""
    try:
        code = validate_language(language)
    except ValueError as exc:
        raise ApiError(422, "validation_error", f"language: {exc}") from exc
    return load_lessons(code)
