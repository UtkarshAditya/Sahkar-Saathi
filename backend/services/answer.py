"""Grounded answer step (role C). Plain Python, no Django imports.

Implements AnswerService from services/types.py:

    question -> B's retriever -> score check -> LLM writes JSON
             -> validate JSON + citations (retry once) -> Answer, or an honest decline

Run the self-test from the backend/ folder (never run this file directly, or
Python will pick up services/types.py instead of the standard library's):

    python -m services.answer
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel

from .llm import MODEL, generate
from .types import Answer, Contact, Passage, Retriever

logger = logging.getLogger(__name__)

# Replace with a verified number from forums.yaml before the demo.
HELPLINE = Contact(label="Helpline", detail="[ADD VERIFIED HELPLINE HERE]")

SYSTEM_PROMPT = """You answer questions about cooperative societies and farmer schemes in India.
Rules:
1. Use ONLY the numbered passages provided. Never use outside knowledge.
2. Copy numbers, dates and deadlines exactly as written in the passages.
3. Every claim must be supported by a passage. List the numbers of the passages you used
   in "cited_ids".
4. If the passages do not contain the answer, set "status" to "declined", leave "cited_ids"
   empty and say you could not find it.
5. Give legal information only. Never predict the outcome of a dispute or say what someone will win.
6. Write the answer in the language requested, in short, simple sentences.
Reply with JSON only, in exactly this shape:
{"status": "answered" or "declined", "answer_text": "...", "cited_ids": [1, 2]}"""


class ModelOutput(BaseModel):
    """What we require the LLM to return."""

    status: Literal["answered", "declined"]
    answer_text: str
    cited_ids: list[int] = []


def build_user_prompt(question: str, passages: list[Passage], language: str) -> str:
    # The model cites passages by position (1, 2, 3...), which small models copy
    # reliably; real chunk ids are long strings that models tend to mangle.
    blocks = [
        f"[{n}] ({p.document_title}, p. {p.page if p.page is not None else 'n/a'}, "
        f"{p.published_date})\n{p.text}"
        for n, p in enumerate(passages, start=1)
    ]
    return (
        "Passages:\n\n"
        + "\n\n".join(blocks)
        + f"\n\nQuestion: {question}\nAnswer language: {language}"
    )


def _parse(raw: str) -> ModelOutput:
    # Some models wrap JSON in ``` fences; strip them before parsing.
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return ModelOutput.model_validate_json(raw)


class GroundedAnswerService:
    """AnswerService implementation: retrieve, check, write, validate."""

    def __init__(self, retriever: Retriever, min_score: float = 0.0, retries: int = 1) -> None:
        # min_score depends on the embedding model's score scale, so re-tune it
        # whenever B changes the embedding model.
        self.retriever = retriever
        self.min_score = min_score
        self.retries = retries

    async def ask(
        self,
        text: str,
        *,
        language: str,
        state: str | None,
        document_id: str | None = None,
    ) -> Answer:
        # TODO Sprint 2: if the question needs a state and state is None, return
        # Answer(needs_state=True, ...) before searching.
        passages = await self.retriever.search(
            text, state=state, language=language, top_k=4, document_id=document_id
        )
        top_score = max((p.score for p in passages), default=None)

        # Check 1: is the evidence strong enough to even try?
        if top_score is None or top_score < self.min_score:
            return self._declined(language, top_score, "low_score")

        user = build_user_prompt(text, passages, language)

        # Check 2: JSON must parse and every cited number must be a real passage.
        for _ in range(self.retries + 1):
            raw = await generate(SYSTEM_PROMPT, user)  # ProviderError propagates to the API
            try:
                out = _parse(raw)
            except ValueError:  # pydantic's ValidationError is a ValueError
                continue
            if out.status == "declined":
                return self._declined(language, top_score, "model_declined")
            if out.cited_ids and all(1 <= i <= len(passages) for i in out.cited_ids):
                cited = [passages[i - 1] for i in dict.fromkeys(out.cited_ids)]
                return Answer(
                    text=out.answer_text,
                    status="answered",
                    language=language,
                    citations=cited,
                    top_score=top_score,
                    model=MODEL,
                )
        return self._declined(language, top_score, "failed_validation")

    def _declined(self, language: str, top_score: float | None, reason: str) -> Answer:
        logger.info("declined: %s (top_score=%s)", reason, top_score)
        return Answer(
            text="I could not find this in the verified documents.",
            status="declined",
            language=language,
            citations=[],
            contact=HELPLINE,
            top_score=top_score,
            model=MODEL,
        )


# ---- Self-test with FAKE data, so you can run this before B's retriever exists.
# The scheme and numbers are invented; never put real facts here from memory.
# Once stubs.py has a retriever, use that instead of FakeRetriever.
def _fake_passage(chunk_id, text, doc_id, title, page, score, date="2026-01-01"):
    return Passage(
        chunk_id=chunk_id,
        text=text,
        document_id=doc_id,
        document_title=title,
        publisher="Test",
        source_url=None,
        published_date=date,
        page=page,
        score=score,
        state=None,
    )


class FakeRetriever:
    async def search(self, query, *, state, language, top_k=4, document_id=None):
        scheme = "Example Scheme Guidelines (test)"
        return [
            _fake_passage(
                "c1",
                "TEST DATA: Under the Example Crop Scheme, a farmer must report crop loss "
                "within 72 hours of the event.",
                "d1",
                scheme,
                page=4,
                score=0.82,
            ),
            _fake_passage(
                "c2",
                "TEST DATA: Losses are reported to the nearest bank branch or the scheme helpline.",
                "d1",
                scheme,
                page=5,
                score=0.74,
            ),
            _fake_passage(
                "c3",
                "TEST DATA: A cooperative society must hold its general body meeting once a year.",
                "d2",
                "Example Model By-laws (test)",
                page=9,
                score=0.41,
                date="2025-06-01",
            ),
        ]


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        service = GroundedAnswerService(FakeRetriever())
        questions = [
            "By when must I report crop loss?",  # should answer, citing passages 1 and 2
            "Who won the cricket match yesterday?",  # not in the passages: should decline
            "Will I win my case against the committee?",  # outcome prediction: should decline
        ]
        for q in questions:
            a = await service.ask(q, language="en", state=None)
            print(f"\nQ: {q}\n  status={a.status}  top_score={a.top_score}  model={a.model}")
            print(f"  text={a.text}")
            print(f"  citations={[(c.document_title, c.page) for c in a.citations]}")

    asyncio.run(_main())
