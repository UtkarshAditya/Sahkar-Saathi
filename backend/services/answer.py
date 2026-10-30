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

from .answer_checks import repeats_question, unsupported_numbers
from .llm import generate, model_name
from .stubs import DEFAULT_CONTACT
from .types import Answer, Contact, Passage, Retriever

logger = logging.getLogger(__name__)

# Shown when the answer is declined. English is the fallback for any other language code.
DECLINE_TEXT = {
    "en": "I could not find this in the verified documents.",
    # hi: machine-written, needs review by a fluent speaker.
    "hi": "मुझे यह जानकारी सत्यापित दस्तावेज़ों में नहीं मिली।",
    # ta: machine-written, needs review by a fluent speaker.
    "ta": "சரிபார்க்கப்பட்ட ஆவணங்களில் இந்தத் தகவலை என்னால் கண்டுபிடிக்க முடியவில்லை.",
}

# The instructions for the LLM. tests/test_answer_prompt.py checks that each rule is present,
# so changing a rule means changing that test on purpose. The JSON shape at the end is what
# ModelOutput validates; do not change one without the other.
SYSTEM_PROMPT = """You answer questions about cooperative societies and farmer schemes in India.
Rules:
1. Use ONLY facts that appear in the numbered passages provided. Never use outside knowledge
   and never guess.
2. Every claim must come from a passage that you cite. List the numbers of the passages you
   used in "cited_ids", and cite only passages that directly support what you say.
3. Do not use a passage about a different procedure, actor or type of case, even if it shares
   words with the question. For example, a rule about refusing to register a new society
   says nothing about a member's deposit in an existing society.
4. If no passage directly answers the question, set "status" to "declined", leave "cited_ids"
   empty and say you could not find it. A decline is better than a wrong answer.
5. Copy numbers, dates, time limits and deadlines exactly as written in the passages. Mention
   a section or rule number only if it appears in the passage you cite.
6. Do not repeat the question. Keep the answer short: at most 3 sentences, or a short list.
7. Give legal information only. Never predict the outcome of a dispute or say what someone
   will win.
8. Write the answer in the language of the question. If you are not sure of the language,
   write in English.
Reply with JSON only, in exactly this shape:
{"status": "answered" or "declined", "answer_text": "...", "cited_ids": [1, 2]}"""

# The question language as a name, so a small model is told "Tamil" and not "ta".
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}


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
    language_name = LANGUAGE_NAMES.get(language, language)
    return (
        "Passages:\n\n"
        + "\n\n".join(blocks)
        + f"\n\nQuestion: {question}\nThe question is written in {language_name}. Answer in "
        "that language (English if you are not sure), using only the passages above; if none "
        "of them directly answers the question, decline."
    )


def _parse(raw: str) -> ModelOutput:
    # Some models wrap JSON in ``` fences; strip them before parsing.
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return ModelOutput.model_validate_json(raw)


class GroundedAnswerService:
    """AnswerService implementation: retrieve, check, write, validate."""

    def __init__(
        self,
        retriever: Retriever,
        min_score: float = 0.0,
        min_score_by_lang: dict[str, float] | None = None,
        retries: int = 1,
        top_k: int = 4,
        contact: Contact | None = None,
        fast_path=None,
    ) -> None:
        # min_score depends on the embedding model's score scale, so re-tune it
        # whenever B changes the embedding model.
        self.retriever = retriever
        self.min_score = min_score
        self.min_score_by_lang = min_score_by_lang or {}
        self.retries = retries
        self.top_k = top_k
        # Who a declined answer points to; the API wiring passes HELPLINE_LABEL/DETAIL.
        self.contact = contact or DEFAULT_CONTACT
        # Optional: answers questions covered by a verified fact in schemes.yaml straight from
        # that fact (services/schemes_fastpath.py). None means every question goes to the model.
        self.fast_path = fast_path

    async def ask(
        self,
        text: str,
        *,
        language: str,
        state: str | None,
        document_id: str | None = None,
    ) -> Answer:
        # "Ask about this document" must stay limited to that document, so skip the fast path.
        if self.fast_path is not None and document_id is None:
            fast = self.fast_path.answer(text, language)
            if fast is not None:
                return fast
        # TODO Sprint 2: if the question needs a state and state is None, return
        # Answer(needs_state=True, ...) before searching.
        passages = await self.retriever.search(
            text, state=state, language=language, top_k=self.top_k, document_id=document_id
        )
        top_score = max((p.score for p in passages), default=None)

        # Check 1: is the evidence strong enough to even try?
        effective_min_score = (
            self.min_score_by_lang.get(language, self.min_score)
            if self.min_score_by_lang
            else self.min_score
        )
        if top_score is None or top_score < effective_min_score:
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
            if repeats_question(text, out.answer_text):
                logger.info("answer repeats the question; retrying")
                continue
            if out.cited_ids and all(1 <= i <= len(passages) for i in out.cited_ids):
                cited = [passages[i - 1] for i in dict.fromkeys(out.cited_ids)]
                invented = unsupported_numbers(out.answer_text, [p.text for p in cited], text)
                if invented:
                    logger.info("answer has numbers not in its sources: %s", sorted(invented))
                    continue
                return Answer(
                    text=out.answer_text,
                    status="answered",
                    language=language,
                    citations=cited,
                    top_score=top_score,
                    model=model_name(),
                )
        return self._declined(language, top_score, "failed_validation")

    def _declined(self, language: str, top_score: float | None, reason: str) -> Answer:
        logger.info("declined: %s (top_score=%s)", reason, top_score)
        return Answer(
            text=DECLINE_TEXT.get(language, DECLINE_TEXT["en"]),
            status="declined",
            language=language,
            citations=[],
            contact=self.contact,
            top_score=top_score,
            model=model_name(),
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
