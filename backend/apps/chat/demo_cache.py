"""Saved answers for the scripted demo conversations (settings.DEMO_CACHE).

With DEMO_CACHE on, /chat/ask serves the saved answer when the question matches a scripted
one, and also when the live services fail on such a question, so the demo cannot be broken
by a stopped LLM or an unreachable vector store. The answers live in data/demo_answers.yaml
with their source and date, or labelled as placeholders; nothing is written here.
"""

import unicodedata
from datetime import date
from functools import cache
from typing import Literal

import yaml
from django.conf import settings
from pydantic import BaseModel, model_validator

from services.types import Answer, Contact, Passage

MODEL_NAME = "demo-cache"


def normalise(text: str) -> str:
    """Case, spacing and punctuation do not matter when matching a question.

    Letters, digits, combining marks and joiners (needed for Hindi and Tamil) are kept;
    punctuation and symbols become spaces, and runs of whitespace collapse to one space.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    kept = (" " if unicodedata.category(ch)[0] in "PSZ" else ch for ch in text)
    return " ".join("".join(kept).split())


class SavedCitation(BaseModel):
    id: str
    document_id: str
    title: str
    publisher: str
    published_date: str | None = None
    page: int | None = None
    section: str | None = None
    url: str | None = None
    excerpt: str | None = None


class SavedAnswer(BaseModel):
    id: str
    conversation: str
    question: str
    language: str
    status: Literal["answered", "partial", "declined"]
    answer_text: str
    followups: list[str] = []
    citations: list[SavedCitation] = []
    source: str
    as_of: date | None = None
    is_placeholder: bool
    needs_review: bool = False

    @model_validator(mode="after")
    def check_rules(self) -> "SavedAnswer":
        if self.status == "declined" and self.citations:
            raise ValueError(f"{self.id}: a declined answer has no citations")
        if self.status != "declined" and not self.citations:
            raise ValueError(f"{self.id}: an answer needs at least one citation")
        if self.status != "declined" and not self.is_placeholder and not self.as_of:
            raise ValueError(f"{self.id}: an answer that is not a placeholder needs an as_of date")
        if not normalise(self.question):
            raise ValueError(f"{self.id}: empty question")
        return self


class SavedAnswersFile(BaseModel):
    answers: list[SavedAnswer]

    @model_validator(mode="after")
    def check_unique(self) -> "SavedAnswersFile":
        ids = [a.id for a in self.answers]
        questions = [normalise(a.question) for a in self.answers]
        if len(set(ids)) != len(ids) or len(set(questions)) != len(questions):
            raise ValueError("saved answer ids and questions must be unique")
        return self


@cache
def load_saved_answers() -> dict[str, SavedAnswer]:
    """Read and validate data/demo_answers.yaml once per process, keyed by the normalised
    question. Raises on invalid content, which the test suite catches before a deploy."""
    path = settings.CONTENT_DIR / "demo_answers.yaml"
    with path.open(encoding="utf-8") as f:
        content = SavedAnswersFile.model_validate(yaml.safe_load(f))
    return {normalise(a.question): a for a in content.answers}


def _to_answer(saved: SavedAnswer) -> Answer:
    # The Passage score is not a retrieval score; 0.0 keeps it from looking like one.
    citations = [
        Passage(
            chunk_id=c.id,
            text=c.excerpt or "",
            document_id=c.document_id,
            document_title=c.title,
            publisher=c.publisher,
            source_url=c.url,
            published_date=c.published_date,
            page=c.page,
            score=0.0,
            state=None,
            section=c.section,
        )
        for c in saved.citations
    ]
    return Answer(
        text=saved.answer_text,
        status=saved.status,
        language=saved.language,
        citations=citations,
        followups=list(saved.followups),
        contact=Contact(settings.HELPLINE_LABEL, settings.HELPLINE_DETAIL)
        if saved.status == "declined"
        else None,
        is_demo=True,
        model=MODEL_NAME,
    )


def lookup(question: str) -> Answer | None:
    """The saved answer for a scripted question, or None. Always marked is_demo."""
    saved = load_saved_answers().get(normalise(question))
    return _to_answer(saved) if saved else None
