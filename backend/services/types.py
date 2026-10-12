"""Contracts between the API layer (member A) and the services (members B and C).

Plain Python, no Django imports. Changing a signature here after sign-off is a pull
request announced in the team chat; a breaking change needs two approvals.

Additions to the original sketch in the Member A plan, all additive:
- ``Passage`` carries ``document_id``, ``publisher`` and ``section`` so the citations
  panel can show them.
- ``Answer`` carries ``contact`` (a declined answer must name who to contact),
  ``is_demo`` (true for stub or cached answers), and ``top_score`` and ``model``, which
  are stored on each Message for evaluation.
- ``AnswerService.ask`` accepts ``document_id`` for "Ask about this document".
- ``Transcript`` carries ``is_demo``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

AnswerStatus = Literal["answered", "partial", "declined"]


@dataclass
class Passage:
    chunk_id: str
    text: str
    document_id: str
    document_title: str
    publisher: str
    source_url: str | None  # None until a verified URL is recorded
    published_date: str  # ISO date
    page: int | None
    score: float
    state: str | None  # None means a central document
    section: str | None = None


class Retriever(Protocol):  # implemented by B
    async def search(
        self,
        query: str,
        *,
        state: str | None,
        language: str | None,
        top_k: int = 4,
        document_id: str | None = None,
    ) -> list[Passage]: ...


@dataclass
class Contact:
    label: str
    detail: str


@dataclass
class Answer:
    text: str
    status: AnswerStatus
    language: str
    citations: list[Passage] = field(default_factory=list)
    needs_state: bool = False
    followups: list[str] = field(default_factory=list)
    contact: Contact | None = None
    is_demo: bool = False
    # For evaluation and debugging; stored on the Message row, never shown to users.
    top_score: float | None = None  # best retrieval score, also when declined
    model: str = ""  # model name that wrote the answer


class AnswerService(Protocol):  # implemented by C
    async def ask(
        self,
        text: str,
        *,
        language: str,
        state: str | None,
        document_id: str | None = None,
    ) -> Answer: ...


@dataclass
class Transcript:
    text: str
    language: str
    confidence: float  # 0..1
    is_demo: bool = False


class SpeechProvider(Protocol):  # implemented by C
    async def transcribe(
        self, audio: bytes, *, content_type: str, language_hint: str | None
    ) -> Transcript: ...

    async def synthesize(self, text: str, *, language: str) -> bytes:
        """Return 16 kHz mono WAV bytes."""
        ...


class ServiceError(Exception):
    """Base for errors a service may raise. The API maps each subclass to a status code."""

    code = "service_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ServiceNotReady(ServiceError):
    """The real implementation is not plugged in yet (and stubs are off)."""

    code = "service_not_ready"


class ProviderError(ServiceError):
    """An upstream provider (LLM, Bhashini, Qdrant) failed or timed out."""

    code = "provider_error"
