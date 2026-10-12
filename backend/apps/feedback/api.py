import uuid

from ninja import Router, Status

from apps.chat.models import Message
from config.errors import ApiError, ErrorOut
from config.throttles import FEEDBACK_THROTTLE
from services.privacy import scrub_pii

from .models import Feedback
from .schemas import FeedbackIn, FeedbackOut

router = Router()


@router.post(
    "",
    response={201: FeedbackOut, 404: ErrorOut, 422: ErrorOut, 429: ErrorOut},
    throttle=[FEEDBACK_THROTTLE],
    summary="Rate an answer or send a comment",
)
async def create_feedback(request, payload: FeedbackIn):
    """Thumbs up/down on an answer (with an optional reason), or a general comment."""
    message = None
    if payload.message_id:
        try:
            message = await Message.objects.aget(pk=uuid.UUID(payload.message_id))
        except (ValueError, Message.DoesNotExist) as exc:
            raise ApiError(404, "message_not_found", "That answer was not found.") from exc

    feedback = await Feedback.objects.acreate(
        message=message,
        rating=payload.rating or "",
        reason=scrub_pii(payload.reason or ""),
        comment=scrub_pii(payload.comment),
    )
    return Status(201, FeedbackOut(id=feedback.id))
