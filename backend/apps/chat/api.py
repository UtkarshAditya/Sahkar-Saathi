import logging
import time
import uuid

from ninja import Router

from config.errors import ErrorOut
from config.services import get_answer_service
from services.stubs import DEFAULT_CONTACT
from services.types import Answer, Passage

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


def _to_response(answer: Answer, conversation_id: str) -> AskOut:
    declined = answer.status == "declined"
    contact = answer.contact or (DEFAULT_CONTACT if declined else None)
    return AskOut(
        conversation_id=conversation_id,
        message_id=uuid.uuid4().hex,
        answer_text=answer.text,
        status=answer.status,
        needs_state=answer.needs_state,
        # Contract: a declined answer has no citations and names a contact.
        citations=[] if declined else [_citation(p) for p in answer.citations],
        followups=answer.followups,
        contact=ContactOut(label=contact.label, detail=contact.detail) if contact else None,
        is_demo=answer.is_demo,
    )


@router.post(
    "/ask",
    response={200: AskOut, 422: ErrorOut, 502: ErrorOut, 503: ErrorOut},
    summary="Ask a question in text",
)
async def ask(request, payload: AskIn):
    """Answer a question from cited public documents, ask for a state, or decline."""
    started = time.perf_counter()
    answer = await get_answer_service().ask(
        payload.text,
        language=payload.language,
        state=payload.state,
        document_id=payload.document_id,
    )
    response = _to_response(answer, payload.conversation_id or uuid.uuid4().hex)
    # Log status and latency only, never the question or answer text.
    logger.info(
        "chat.ask status=%s needs_state=%s citations=%d language=%s latency_ms=%d",
        response.status,
        response.needs_state,
        len(response.citations),
        payload.language,
        (time.perf_counter() - started) * 1000,
    )
    return response
