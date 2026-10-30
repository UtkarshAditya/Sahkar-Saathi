"""Tests for the echo check and the answer service's use of it (role C).

They use a fake retriever and a fake LLM, so they need no Ollama and no database.
Run from backend/:  python -m pytest tests/test_answer_checks.py -v
"""

import asyncio
import json

from services import answer as answer_module
from services.answer import GroundedAnswerService
from services.answer_checks import normalize_text, repeats_question
from services.types import Passage

QUESTION = "By when must I report crop loss?"


def _passage() -> Passage:
    return Passage(
        chunk_id="c1",
        text="TEST DATA: a farmer must report crop loss within 72 hours of the event.",
        document_id="d1",
        document_title="Example Scheme Guidelines (test)",
        publisher="Test",
        source_url=None,
        published_date="2026-01-01",
        page=4,
        score=0.9,
        state=None,
    )


class _Retriever:
    async def search(self, query, *, state, language, top_k=4, document_id=None):
        return [_passage()]


def _ask(monkeypatch, replies, question=QUESTION):
    """Run the service with a fake LLM that returns each reply in turn. Returns (answer, calls)."""
    calls = []

    async def fake_generate(system, user, **kwargs):
        calls.append(user)
        return replies[min(len(calls), len(replies)) - 1]

    monkeypatch.setattr(answer_module, "generate", fake_generate)
    service = GroundedAnswerService(_Retriever(), min_score=0.0)
    return asyncio.run(service.ask(question, language="en", state=None)), calls


def _reply(text, cited=(1,), status="answered"):
    return json.dumps({"status": status, "answer_text": text, "cited_ids": list(cited)})


# ---- the echo check on its own ----


def test_exact_repeat_is_flagged():
    assert repeats_question(QUESTION, "By when must I report crop loss?")


def test_repeat_with_different_case_and_punctuation_is_flagged():
    assert repeats_question(QUESTION, "by when must i report crop loss")


def test_question_repeated_twice_with_a_short_addition_is_flagged():
    answer = f"{QUESTION} {QUESTION} Write to the bank."
    assert repeats_question(QUESTION, answer)


def test_hindi_repeat_is_flagged_even_with_a_danda():
    question = "फसल के नुकसान की सूचना कब देनी चाहिए?"
    assert repeats_question(question, "फसल के नुकसान की सूचना कब देनी चाहिए ।")


def test_real_answer_that_reuses_a_few_words_is_not_flagged():
    assert not repeats_question(QUESTION, "You must report crop loss within 72 hours.")


def test_answer_that_restates_most_but_not_all_of_a_long_question_is_not_flagged():
    question = "Can a member attend the general body meeting of the society?"
    assert not repeats_question(question, "Yes, you can attend the general body meeting.")


def test_very_short_question_is_never_flagged():
    assert not repeats_question("Who are you?", "Who are you? I am an assistant.")


def test_normalize_keeps_vowel_signs_and_drops_punctuation():
    assert normalize_text("फसल बीमा कब? ।") == "फसल बीमा कब"


# ---- the service ----


def test_echoed_answer_is_retried_and_then_declined(monkeypatch):
    result, calls = _ask(monkeypatch, [_reply(QUESTION)])
    assert result.status == "declined"
    assert result.citations == []
    assert len(calls) == 2  # first try plus one retry


def test_echo_is_recovered_if_the_retry_gives_a_real_answer(monkeypatch):
    result, calls = _ask(monkeypatch, [_reply(QUESTION), _reply("Report it within 72 hours.")])
    assert result.status == "answered"
    assert result.text == "Report it within 72 hours."
    assert len(calls) == 2


def test_normal_answer_is_unaffected(monkeypatch):
    result, calls = _ask(monkeypatch, [_reply("Report it within 72 hours.")])
    assert result.status == "answered"
    assert [c.chunk_id for c in result.citations] == ["c1"]
    assert len(calls) == 1
