"""Wiring: one function per service interface.

Handlers call only these functions, so swapping a stub for the real implementation never
touches an endpoint. With ``USE_STUBS`` on, each returns its stub from ``services.stubs``.
With it off, each returns the real implementation, or raises ``ServiceNotReady`` (HTTP 503)
until that implementation is plugged in below.
"""

from functools import cache

from django.conf import settings

from services.stubs import StubAnswerService, StubRetriever, StubSpeechProvider
from services.types import AnswerService, Retriever, ServiceNotReady, SpeechProvider


def get_retriever() -> Retriever:
    return _retriever(settings.USE_STUBS)


def get_answer_service() -> AnswerService:
    return _answer_service(settings.USE_STUBS)


def get_speech_provider() -> SpeechProvider:
    return _speech_provider(settings.USE_STUBS)


# Cached per USE_STUBS value, so real services (models, clients) are built once.


@cache
def _retriever(use_stubs: bool) -> Retriever:
    if use_stubs:
        return StubRetriever()
    # Member B: return the Qdrant-backed retriever from services/retrieval/ here.
    raise ServiceNotReady("The retriever is not connected yet. Set USE_STUBS=true.")


@cache
def _answer_service(use_stubs: bool) -> AnswerService:
    if use_stubs:
        return StubAnswerService(StubRetriever(), score_threshold=settings.SCORE_THRESHOLD)
    # Member C: return the agent / grounded answer service here, built with get_retriever().
    raise ServiceNotReady("The answer service is not connected yet. Set USE_STUBS=true.")


@cache
def _speech_provider(use_stubs: bool) -> SpeechProvider:
    if use_stubs:
        return StubSpeechProvider()
    # Member C: return the Bhashini provider (with Whisper fallback) from services/speech/ here.
    raise ServiceNotReady("The speech service is not connected yet. Set USE_STUBS=true.")
