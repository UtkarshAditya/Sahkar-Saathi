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

from .types import (
    Answer,
    Contact,
    GrievanceCategory,
    GrievanceResult,
    Passage,
    Transcript,
)

STUB_MODEL = "stub"
COVERED_STATE = "TN"  # the one state whose Act is in the corpus (team decision)

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
        chunk_id="stub-tn-act-18",
        text="Stub passage about the management of cooperative societies.",
        document_id="doc-tn-act",
        document_title="Tamil Nadu Co-operative Societies Act, 1983",
        publisher="Sample metadata",
        source_url=None,
        published_date="2024-03-01",
        page=18,
        score=0.74,
        state="TN",
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
        score_threshold: float | None = None,
    ) -> list[Passage]:
        q = query.lower()
        if _looks_like_gibberish(q):
            hits = [_with_score(_CANNED[0], 0.12)]  # below any sensible threshold
        elif _contains(q, _PMFBY_WORDS):
            hits = [_CANNED[0]]
        elif _contains(q, _LAW_WORDS):
            hits = [p for p in _CANNED[1:] if p.state in (None, state)]
        else:
            hits = [_with_score(_CANNED[2], 0.2)]
        if document_id:
            hits = [p for p in hits if p.document_id == document_id] or hits
        if score_threshold is not None:
            hits = [p for p in hits if p.score >= score_threshold]
        return hits[:top_k]


def _with_score(p: Passage, score: float) -> Passage:
    return Passage(**{**p.__dict__, "score": score})


class StubAnswerService:
    """Wraps the stub retriever. Replaced by C's agent and grounded answer step."""

    def __init__(
        self,
        retriever: StubRetriever,
        score_threshold: float = 0.5,
        covered_state: str = COVERED_STATE,
    ) -> None:
        self.retriever = retriever
        self.score_threshold = score_threshold
        self.covered_state = covered_state

    async def ask(
        self,
        text: str,
        *,
        language: str,
        state: str | None,
        document_id: str | None = None,
    ) -> Answer:
        answer = await self._answer(text, language=language, state=state, document_id=document_id)
        answer.model = STUB_MODEL
        return answer

    async def _answer(
        self, text: str, *, language: str, state: str | None, document_id: str | None
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
        top_score = max((p.score for p in passages), default=None)
        if top_score is None or top_score < self.score_threshold:
            answer = self._decline(
                language, "I could not find this in my sources, so I will not guess."
            )
            answer.top_score = top_score
            return answer

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
                top_score=top_score,
            )

        covered = state == self.covered_state
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
            top_score=top_score,
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
    # ta: machine-written, needs review by a fluent speaker.
    "ta": "பிஎம்எஃப்பிஒய் திட்டத்தின் கீழ் காப்பீடு செய்யப்பட்ட என் பயிர் சேதமடைந்தால் நான் என்ன செய்ய வேண்டும்?",
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


# --- Grievance guide --------------------------------------------------------------------
# Sample categories and forums. Member C replaces these with forums.yaml (verified
# authorities per state) and the agent's category detection.

_GRIEVANCE_CATEGORIES: list[tuple[GrievanceCategory, tuple[str, ...]]] = [
    (
        GrievanceCategory(
            "deposit-refund",
            "Deposit or share money not returned",
            "The society has not refunded a deposit, share capital or dividend.",
        ),
        ("deposit", "refund", "share", "dividend", "money back"),
    ),
    (
        GrievanceCategory(
            "membership",
            "Membership refused or removed",
            "You were refused membership or removed without a proper reason.",
        ),
        ("membership", "expelled", "removed", "refused"),
    ),
    (
        GrievanceCategory(
            "election",
            "Election of the board",
            "Concerns about how a board election was announced or conducted.",
        ),
        ("election", "vote", "board", "director"),
    ),
    (
        GrievanceCategory(
            "records",
            "Accounts or records not shared",
            "You asked to see accounts, audit reports or minutes and were refused.",
        ),
        ("accounts", "audit", "records", "minutes", "balance sheet"),
    ),
    (
        GrievanceCategory(
            "loan",
            "Loan or dues dispute",
            "Disagreement about a loan, interest charged or dues recovered.",
        ),
        ("loan", "interest", "dues", "recovery", "kcc"),
    ),
    (
        GrievanceCategory(
            "crop-insurance",
            "Crop insurance claim",
            "A PMFBY claim was delayed, rejected or wrongly calculated.",
        ),
        ("crop", "insurance", "pmfby", "claim", "bima"),
    ),
]

_REGISTRAR = "Registrar of Co-operative Societies, district office"
_INSURANCE_FORUM = "Insurance company grievance cell, then the district grievance committee"


class StubGrievanceGuide:
    """Keyword category detection and a template draft. Never files anything."""

    def categories(self) -> list[GrievanceCategory]:
        return [category for category, _ in _GRIEVANCE_CATEGORIES]

    async def guide(
        self,
        description: str,
        *,
        state: str | None,
        language: str,
        category_hint: str | None = None,
    ) -> GrievanceResult:
        category = self._detect(description, category_hint)
        insurance = category.id == "crop-insurance"
        forum = _INSURANCE_FORUM if insurance else _REGISTRAR
        state_text = state or "[Your state]"
        draft = (
            f"To,\n{forum}\n{state_text}\n\n"
            f"Subject: Complaint regarding {category.label.lower()}\n\n"
            "Respected Sir/Madam,\n\n"
            "I am a member of [name of cooperative society], [village/taluk], "
            f"{state_text}, with membership number [membership number].\n\n"
            f"{description.strip()}\n\n"
            "I first raised this with the society on [date] but have not received a "
            "resolution. I request you to look into this matter and take appropriate action.\n\n"
            "Copies of the relevant documents are enclosed.\n\n"
            "Yours faithfully,\n[Your name]\n[Address]\n[Date]"
        )
        return GrievanceResult(
            category=category,
            forum=f"{forum} (sample forum)",
            forum_note=(
                "Sample forum. The verified route and helpline will come from forums.yaml."
                if insurance
                else "Sample forum. The exact authority depends on your state Act and will be "
                "confirmed from forums.yaml."
            ),
            steps=[
                "Write to the secretary or board of your society first, and keep a dated copy.",
                "Wait for a reply for a reasonable period. Note the date if there is no response.",
                f"If unresolved, send the complaint below to the {forum}.",
                "Attach copies (never originals) of the documents in the checklist.",
                "Keep the acknowledgement or receipt number and follow up if needed.",
            ],
            documents_needed=[
                "Proof of membership (pass book or share certificate)",
                "Copy of your earlier letter to the society, with date",
                "Receipts, statements or notices related to the problem",
                "Any reply received from the society",
                "Identity proof (show only, do not leave originals)",
            ],
            draft_text=draft,
            is_demo=True,
        )

    @staticmethod
    def _detect(description: str, hint: str | None) -> GrievanceCategory:
        if hint:
            for category, _ in _GRIEVANCE_CATEGORIES:
                if category.id == hint:
                    return category
        text = description.lower()
        for category, keywords in _GRIEVANCE_CATEGORIES:
            if any(k in text for k in keywords):
                return category
        return _GRIEVANCE_CATEGORIES[0][0]
