"""Wiring: one function per service interface.

Handlers call only these functions, so swapping a stub for the real implementation never
touches an endpoint. Each service has its own flag (settings.USE_STUB_RETRIEVER,
USE_STUB_ANSWER, USE_STUB_SPEECH, USE_STUB_GRIEVANCE; all default to USE_STUBS), so
services can be switched on one at a time. A real service that is not plugged in yet
raises ``ServiceNotReady`` (HTTP 503) naming the flag to set.
"""

import logging
from functools import cache

from django.conf import settings

from services.stubs import (
    StubAnswerService,
    StubGrievanceGuide,
    StubRetriever,
    StubSpeechProvider,
)
from services.types import (
    AnswerService,
    Contact,
    GrievanceGuide,
    Retriever,
    ServiceNotReady,
    SpeechProvider,
)

logger = logging.getLogger("sahkar.services")


def get_retriever() -> Retriever:
    return _retriever(settings.USE_STUB_RETRIEVER)


def get_answer_service() -> AnswerService:
    # Keyed by the retriever flag too, because the real answer service wraps a retriever.
    return _answer_service(settings.USE_STUB_ANSWER, settings.USE_STUB_RETRIEVER)


def get_speech_provider() -> SpeechProvider:
    return _speech_provider(settings.USE_STUB_SPEECH)


def get_grievance_guide() -> GrievanceGuide:
    return _grievance_guide(settings.USE_STUB_GRIEVANCE)


# Cached per flag value, so real services (models, clients) are built once.


@cache
def _retriever(use_stub: bool) -> Retriever:
    if use_stub:
        return StubRetriever()
    from services.retrieval.qdrant_retriever import QdrantRetriever

    return QdrantRetriever()


@cache
def _answer_service(use_stub: bool, use_stub_retriever: bool) -> AnswerService:
    if use_stub:
        return StubAnswerService(
            StubRetriever(),
            score_threshold=settings.SCORE_THRESHOLD,
            covered_state=settings.COVERED_STATE_CODE,
        )
    from services.answer import GroundedAnswerService

    return GroundedAnswerService(
        _retriever(use_stub_retriever),
        min_score=settings.SCORE_THRESHOLD,
        top_k=settings.TOP_K,
        contact=Contact(label=settings.HELPLINE_LABEL, detail=settings.HELPLINE_DETAIL),
    )


@cache
def _speech_provider(use_stub: bool) -> SpeechProvider:
    if use_stub:
        return StubSpeechProvider()
    # faster_whisper itself is imported lazily, on the first transcription.
    from services.speech.whisper_provider import WhisperSpeechProvider

    logger.warning(
        "Speech: Whisper transcribes; synthesis (Listen) is still the stub's silent audio."
    )
    return WhisperSpeechProvider(synthesizer=StubSpeechProvider())


@cache
def _grievance_guide(use_stub: bool) -> GrievanceGuide:
    if use_stub:
        return StubGrievanceGuide()
    # Member C: return the forums.yaml-backed guide here.
    raise ServiceNotReady("The grievance guide is not connected yet. Set USE_STUB_GRIEVANCE=true.")
