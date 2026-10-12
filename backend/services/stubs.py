"""Stub implementations of the service interfaces, served while ``USE_STUBS`` is on.

They are realistic enough to exercise every state of the contract:
- answered with citations (PMFBY questions score high),
- needs_state (by-law questions without a state),
- partial (a state that is not in the knowledge base),
- declined with a contact (gibberish or out-of-scope questions score low).

Every answer is marked ``is_demo=True``; none of it is verified legal guidance.
Plain Python, no Django imports.
"""

from __future__ import annotations

import io
import re
import wave

from .types import Answer, Contact, Passage, Transcript

COVERED_STATE = "MH"  # the one state whose Act is in the corpus (team decision)

DEFAULT_CONTACT = Contact(
    label="Your district cooperative office (Registrar of Co-operative Societies)",
    detail="Verified helpline numbers will be added from forums.yaml.",
)

_PMFBY_WORDS = ("pmfby", "crop", "insurance", "fasal", "bima", "फसल", "बीमा")
_LAW_WORDS = ("by-law", "bylaw", "bye-law", "board", "election", "member", "society", "pacs")
_OUT_OF_SCOPE = ("win my", "will i win", "predict", "lawyer", "cricket", "stock market")

_CANNED: list[Passage] = [
    Passage(
        chunk_id="stub-pmfby-34",
        text="Stub passage about reporting crop loss under PMFBY.",
        document_id="doc-pmfby-guidelines",
        document_title="PMFBY Operational Guidelines",
        publisher="Sample metadata",
        source_url=None,
        published_date="2026-01-15",
        page=34,
        score=0.82,
        state=None,
        section="Localised calamities (sample section)",
    ),
    Passage(
        chunk_id="stub-mh-act-18",
        text="Stub passage about the management of cooperative societies.",
        document_id="doc-mh-act",
        document_title="Maharashtra Co-operative Societies Act, 1960",
        publisher="Sample metadata",
        source_url=None,
        published_date="2024-03-01",
        page=18,
        score=0.74,
        state="MH",
        section="Management of societies (sample section)",
    ),
    Passage(
        chunk_id="stub-bylaws-12",
        text="Stub passage about the board of directors of a PACS.",
        document_id="doc-model-bylaws-en",
        document_title="Model Bye-laws for PACS",
        publisher="Sample metadata",
        source_url=None,
        published_date="2023-01-05",
        page=12,
        score=0.71,
        state=None,
        section="Board of directors (sample section)",
    ),
]


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _looks_like_gibberish(text: str) -> bool:
    letters = re.findall(r"\w", text)
    return len(letters) < 3 or len(text.split()) < 2


class StubRetriever:
    """Canned passages with scores. Replaced by B's Qdrant-backed retriever."""

    async def search(
        self,
        query: str,
        *,
        state: str | None,
        language: str | None,
        top_k: int = 4,
        document_id: str | None = None,
    ) -> list[Passage]:
        q = query.lower()
        if _looks_like_gibberish(q):
            return [_with_score(_CANNED[0], 0.12)]  # below any sensible threshold
        if _contains(q, _PMFBY_WORDS):
            hits = [_CANNED[0]]
        elif _contains(q, _LAW_WORDS):
            hits = [p for p in _CANNED[1:] if p.state in (None, state)]
        else:
            hits = [_with_score(_CANNED[2], 0.2)]
        if document_id:
            hits = [p for p in hits if p.document_id == document_id] or hits
        return hits[:top_k]


def _with_score(p: Passage, score: float) -> Passage:
    return Passage(**{**p.__dict__, "score": score})


class StubAnswerService:
    """Wraps the stub retriever. Replaced by C's agent and grounded answer step."""

    def __init__(self, retriever: StubRetriever, score_threshold: float = 0.5) -> None:
        self.retriever = retriever
        self.score_threshold = score_threshold

    async def ask(
        self,
        text: str,
        *,
        language: str,
        state: str | None,
        document_id: str | None = None,
    ) -> Answer:
        q = text.lower()

        if _contains(q, _OUT_OF_SCOPE):
            return self._decline(
                language,
                "I can explain what public cooperative documents say, but I cannot predict "
                "the outcome of a dispute or give legal advice.",
            )

        if _contains(q, _LAW_WORDS) and not _contains(q, _PMFBY_WORDS) and not state:
            return Answer(
                text="Cooperative law differs by state. Which state is your society registered in?",
                status="partial",
                language=language,
                needs_state=True,
                is_demo=True,
            )

        passages = await self.retriever.search(
            text, state=state, language=language, document_id=document_id
        )
        if not passages or max(p.score for p in passages) < self.score_threshold:
            return self._decline(
                language, "I could not find this in my sources, so I will not guess."
            )

        if _contains(q, _PMFBY_WORDS):
            return Answer(
                text=(
                    "Stub answer: report crop loss as early as possible to the insurance "
                    "company, your bank or the agriculture office. The exact time limit will "
                    "be quoted from the verified PMFBY guidelines."
                ),
                status="answered",
                language=language,
                citations=passages,
                followups=["Which documents do I need for a crop loss claim?"],
                is_demo=True,
            )

        covered = state == COVERED_STATE
        return Answer(
            text=(
                "Stub answer: board members are generally elected by members at the general "
                "body meeting, following the state Act and the society's registered by-laws."
                if covered
                else "Stub answer: your state is not in the knowledge base yet, so this uses "
                "only the central documents and the model by-laws."
            ),
            status="answered" if covered else "partial",
            language=language,
            citations=passages,
            followups=["Who conducts elections in a cooperative society?"],
            is_demo=True,
        )

    @staticmethod
    def _decline(language: str, text: str) -> Answer:
        return Answer(
            text=text,
            status="declined",
            language=language,
            contact=DEFAULT_CONTACT,
            followups=["Where can I file a complaint against my cooperative society?"],
            is_demo=True,
        )


_STUB_TRANSCRIPTS = {
    "en": "What should I do if my insured crop is damaged under PMFBY?",
    "hi": "अगर पीएमएफबीवाई के तहत मेरी बीमित फसल खराब हो जाए तो मुझे क्या करना चाहिए?",
}


class StubSpeechProvider:
    """A fixed transcript and a short silent WAV. Replaced by C's Bhashini/Whisper provider."""

    sample_rate = 16_000

    async def transcribe(
        self, audio: bytes, *, content_type: str, language_hint: str | None
    ) -> Transcript:
        language = language_hint if language_hint in _STUB_TRANSCRIPTS else "en"
        return Transcript(
            text=_STUB_TRANSCRIPTS[language], language=language, confidence=0.9, is_demo=True
        )

    async def synthesize(self, text: str, *, language: str) -> bytes:
        # About 60 ms of silence per word, capped at 5 seconds: 16 kHz, mono, 16-bit.
        seconds = min(5.0, max(0.5, 0.06 * len(text.split())))
        frames = int(self.sample_rate * seconds)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"\x00\x00" * frames)
        return buffer.getvalue()
