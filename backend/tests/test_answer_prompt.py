"""The prompt services/answer.py sends to the LLM, with a fake LLM: no model, no network.

These tests check that the instructions are in the prompt and that the service sends them. They
cannot show that a real model obeys them; that is what scripts/acceptance.py is for."""

import asyncio
import json

import pytest

from services import answer as answer_module
from services.answer import (
    LANGUAGE_NAMES,
    SYSTEM_PROMPT,
    GroundedAnswerService,
    ModelOutput,
    build_user_prompt,
)
from services.types import Passage


def passage(n: int, text: str = "A rule.", page: int | None = 3, score: float = 0.9) -> Passage:
    return Passage(
        chunk_id=f"c{n}",
        text=text,
        document_id=f"DOC-{n}",
        document_title=f"Document {n}",
        publisher="Test",
        source_url=None,
        published_date="2024-01-01",
        page=page,
        score=score,
        state=None,
    )


# --- The instructions are in the system prompt ----------------------------------------


@pytest.mark.parametrize(
    "needle",
    [
        # 1. only facts from the passages
        "ONLY facts that appear in the numbered passages",
        "never guess",
        # 2. every claim from a cited passage
        "Every claim must come from a passage that you cite",
        '"cited_ids"',
        "directly support",
        # 3. a passage about a different procedure, actor or type of case is not to be used
        "different procedure, actor or type of case",
        "refusing to register a new society",
        "member's deposit in an existing society",
        # 4. decline when nothing directly answers
        "If no passage directly answers the question",
        '"declined"',
        "A decline is better than a wrong answer",
        # 5. exact numbers; section numbers only when the passage has them
        "Copy numbers, dates, time limits and deadlines exactly",
        "only if it appears in the passage you cite",
        # 6. no echo, short
        "Do not repeat the question",
        "at most 3 sentences",
        # 7. legal information only
        "Never predict the outcome of a dispute",
        # 8. the language of the question, English when unsure
        "in the language of the question",
        "not sure of the language",
    ],
)
def test_the_system_prompt_contains_each_instruction(needle):
    assert needle in " ".join(SYSTEM_PROMPT.split())


def test_the_json_shape_is_unchanged():
    assert SYSTEM_PROMPT.rstrip().endswith(
        '{"status": "answered" or "declined", "answer_text": "...", "cited_ids": [1, 2]}'
    )
    assert set(ModelOutput.model_fields) == {"status", "answer_text", "cited_ids"}


def test_the_rules_are_numbered_in_order():
    numbers = [line.split(".")[0] for line in SYSTEM_PROMPT.splitlines() if line[:1].isdigit()]
    assert numbers == [str(n) for n in range(1, 9)]


# --- The user prompt ------------------------------------------------------------------


def test_passages_are_numbered_from_one_with_title_page_and_date():
    prompt = build_user_prompt(
        "What is X?", [passage(1, "First."), passage(2, "Second.", None)], "en"
    )
    assert "[1] (Document 1, p. 3, 2024-01-01)\nFirst." in prompt
    assert "[2] (Document 2, p. n/a, 2024-01-01)\nSecond." in prompt
    assert prompt.index("[1]") < prompt.index("[2]") < prompt.index("Question: What is X?")


@pytest.mark.parametrize(("code", "name"), [("en", "English"), ("hi", "Hindi"), ("ta", "Tamil")])
def test_the_question_language_is_named_not_coded(code, name):
    prompt = build_user_prompt("Q?", [passage(1)], code)
    assert f"The question is written in {name}" in prompt
    assert name == LANGUAGE_NAMES[code]


def test_an_unknown_language_code_is_passed_through():
    assert "written in mr." in build_user_prompt("Q?", [passage(1)], "mr")


def test_the_user_prompt_repeats_the_key_instructions_next_to_the_question():
    """Small models follow the last lines best, so the reminders sit after the question."""
    prompt = build_user_prompt("Q?", [passage(1)], "en")
    tail = " ".join(prompt.split("Question: Q?")[1].split())
    assert "English if you are not sure" in tail
    assert "using only the passages above" in tail
    assert "directly answers the question, decline" in tail


# --- The service sends them -----------------------------------------------------------


class OnePassageRetriever:
    async def search(self, query, *, state, language, top_k=4, document_id=None):
        return [passage(1, "The Registrar may refuse to register a society.")]


def run_service(monkeypatch, reply: dict, *, language="en"):
    sent = []

    async def fake_generate(system, user, json_mode=True, temperature=0.0):
        sent.append({"system": system, "user": user})
        return json.dumps(reply)

    monkeypatch.setattr(answer_module, "generate", fake_generate)
    service = GroundedAnswerService(OnePassageRetriever(), min_score=0.5)
    result = asyncio.run(service.ask("Can I get my deposit back?", language=language, state="TN"))
    return result, sent


def test_the_service_sends_the_system_prompt_and_the_numbered_passages(monkeypatch):
    result, sent = run_service(
        monkeypatch, {"status": "answered", "answer_text": "A.", "cited_ids": [1]}
    )
    assert result.status == "answered"
    assert sent[0]["system"] == SYSTEM_PROMPT
    assert "[1] (Document 1" in sent[0]["user"]
    assert "Question: Can I get my deposit back?" in sent[0]["user"]


def test_the_service_names_the_language_it_was_given(monkeypatch):
    _, sent = run_service(
        monkeypatch, {"status": "declined", "answer_text": "-", "cited_ids": []}, language="ta"
    )
    assert "The question is written in Tamil" in sent[0]["user"]


def test_a_model_decline_is_still_a_decline_without_citations(monkeypatch):
    """The decline path the new instructions steer towards works as before."""
    result, _ = run_service(
        monkeypatch, {"status": "declined", "answer_text": "Not found.", "cited_ids": []}
    )
    assert result.status == "declined" and result.citations == []
    assert result.contact is not None


def test_validation_is_unchanged_a_citation_out_of_range_is_declined(monkeypatch):
    result, sent = run_service(
        monkeypatch, {"status": "answered", "answer_text": "A.", "cited_ids": [9]}
    )
    assert result.status == "declined"
    assert len(sent) == 2, "one retry, as before"
