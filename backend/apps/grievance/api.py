"""Guided complaint help. The service suggests a forum, steps and a draft; it never files.

Saving GrievanceCase rows (only when STORE_MESSAGES is on) is a Sprint 2 task.
"""

import logging
from dataclasses import asdict

from ninja import Router

from config.errors import ApiError, ErrorOut
from config.services import get_grievance_guide
from config.throttles import GRIEVANCE_THROTTLE

from .schemas import GrievanceCategoryOut, GrievanceGuideOut, GrievanceIn

logger = logging.getLogger("sahkar.api.grievance")

router = Router()


@router.get(
    "/categories",
    response={200: list[GrievanceCategoryOut], 503: ErrorOut},
    summary="Grievance categories",
)
def categories(request):
    """Categories the user can pick before asking for guidance."""
    return [GrievanceCategoryOut(**asdict(c)) for c in get_grievance_guide().categories()]


@router.post(
    "/guide",
    response={200: GrievanceGuideOut, 422: ErrorOut, 429: ErrorOut, 502: ErrorOut, 503: ErrorOut},
    throttle=[GRIEVANCE_THROTTLE],
    summary="Guided complaint help",
)
async def guide(request, payload: GrievanceIn):
    """Category, forum, steps, a documents checklist and an editable draft.

    Nothing is submitted to any office. The draft contains [placeholders] for the
    member's own details, which the client never sends back.
    """
    service = get_grievance_guide()
    if payload.category_hint and payload.category_hint not in {c.id for c in service.categories()}:
        raise ApiError(422, "validation_error", "category_hint: Unknown category.")

    result = await service.guide(
        payload.description,
        state=payload.state,
        language=payload.language,
        category_hint=payload.category_hint,
    )
    logger.info("grievance.guide category=%s language=%s", result.category.id, payload.language)
    return GrievanceGuideOut(
        category=GrievanceCategoryOut(**asdict(result.category)),
        forum=result.forum,
        forum_note=result.forum_note,
        steps=result.steps,
        documents_needed=result.documents_needed,
        draft_text=result.draft_text,
        is_demo=result.is_demo,
    )
