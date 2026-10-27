import logging
import time
import uuid

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import DatabaseError, transaction
from ninja import Router

from config.errors import ErrorOut
from config.services import get_answer_service
from config.throttles import CHAT_THROTTLE
from services.privacy import scrub_pii
from services.stubs import DEFAULT_CONTACT
from services.types import Answer, Passage

from . import demo_cache
from .models import Citation, Conversation, Message
from .schemas import AskIn, AskOut, CitationOut, ContactOut

logger = logging.getLogger("sahkar.api.chat")

router = Router()


def _citation(p: Passage) -> CitationOut:
    return CitationOut(
        id=p.chunk_id,
        document_id=p.document_id,
        title=p.document_title,
        publisher=p.publisher,
        published_date=p.published_date,
        page=p.page,
        section=p.section,
        url=p.source_url,
        excerpt=p.text[:300] if p.text else None,
    )


def _normalise(answer: Answer) -> Answer:
    """Enforce the contract: a declined answer has no citations and names a contact."""
    if answer.status == "declined":
        answer.citations = []
        answer.contact = answer.contact or DEFAULT_CONTACT
    return answer


async def _answer(payload: AskIn) -> Answer:
    """The saved answer for a scripted question when DEMO_CACHE is on, else the live service.

    If the live service fails on a scripted question, the saved answer is served instead of
    an error. Any other question surfaces the failure as usual.
    """
    if settings.DEMO_CACHE and not payload.document_id:
        # "Ask about this document" is a different question from the scripted one.
        if (saved := demo_cache.lookup(payload.text)) is not None:
            return saved
    try:
        return await get_answer_service().ask(
            payload.text,
            language=payload.language,
            state=payload.state,
            document_id=payload.document_id,
        )
    except Exception as exc:
        # Not only ProviderError and ServiceNotReady: the vector store's own errors are not
        # wrapped yet, and a live demo must not end on a 500 when a saved answer exists.
        if settings.DEMO_CACHE and (saved := demo_cache.lookup(payload.text)) is not None:
            logger.warning("chat.ask served the demo cache after %s", exc.__class__.__name__)
            return saved
        raise


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def _store(payload: AskIn, answer: Answer, latency_ms: int) -> tuple[uuid.UUID, uuid.UUID]:
    """Save the exchange; returns (conversation_id, message_id). Synchronous on purpose:
    Django has no async transactions, so this runs in a thread via sync_to_async."""
    keep_text = settings.STORE_MESSAGES
    with transaction.atomic():
        existing = _parse_uuid(payload.conversation_id)
        conversation = (
            Conversation.objects.filter(pk=existing).first() if existing else None
        ) or Conversation.objects.create()
        conversation.save(update_fields=["last_activity_at"])

        message = Message.objects.create(
            conversation=conversation,
            question_text=scrub_pii(payload.text) if keep_text else "",
            answer_text=scrub_pii(answer.text) if keep_text else "",
            language=payload.language,
            state=payload.state or "",
            document_id=payload.document_id or "",
            status=answer.status,
            needs_state=answer.needs_state,
            top_score=answer.top_score,
            model_name=answer.model[:100],
            latency_ms=latency_ms,
            is_demo=answer.is_demo,
        )
        Citation.objects.bulk_create(
            Citation(
                message=message,
                rank=rank,
                chunk_id=p.chunk_id[:100],
                document_id=p.document_id[:64],
                document_title=p.document_title[:300],
                page=p.page,
                score=p.score,
            )
            for rank, p in enumerate(answer.citations, start=1)
        )
    return conversation.id, message.id


@router.post(
    "/ask",
    response={200: AskOut, 422: ErrorOut, 429: ErrorOut, 502: ErrorOut, 503: ErrorOut},
    throttle=[CHAT_THROTTLE],
    summary="Ask a question in text",
)
async def ask(request, payload: AskIn):
    """Answer a question from cited public documents, ask for a state, or decline.

    Pass the returned ``conversation_id`` back with follow-up questions. The returned
    ``message_id`` is what ``POST /feedback`` rates.
    """
    started = time.perf_counter()
    answer = _normalise(await _answer(payload))
    latency_ms = int((time.perf_counter() - started) * 1000)

    try:
        conversation_id, message_id = await sync_to_async(_store)(payload, answer, latency_ms)
    except DatabaseError:
        # Still answer the user; the exchange just cannot be rated or evaluated later.
        logger.exception("chat.ask could not store the message")
        conversation_id, message_id = uuid.uuid4(), uuid.uuid4()

    # Log status and latency only, never the question or answer text.
    logger.info(
        "chat.ask status=%s needs_state=%s citations=%d language=%s top_score=%s latency_ms=%d",
        answer.status,
        answer.needs_state,
        len(answer.citations),
        payload.language,
        answer.top_score,
        latency_ms,
    )
    contact = answer.contact
    return AskOut(
        conversation_id=conversation_id.hex,
        message_id=message_id.hex,
        answer_text=answer.text,
        status=answer.status,
        needs_state=answer.needs_state,
        citations=[_citation(p) for p in answer.citations],
        followups=answer.followups,
        contact=ContactOut(label=contact.label, detail=contact.detail) if contact else None,
        is_demo=answer.is_demo,
    )
