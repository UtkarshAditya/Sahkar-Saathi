"""POST /chat/ask through the real GroundedAnswerService (USE_STUB_ANSWER=false) over the
stub retriever. The LLM is faked by replacing services.answer.generate: no network."""

import json

import pytest

from apps.chat.models import Message
from config import services
from services import answer as answer_module
from services.answer import DECLINE_TEXT
from services.types import ProviderError

URL = "/api/v1/chat/ask"
QUESTION = "What should I do if my insured crop is damaged under PMFBY?"


def ask(client, text=QUESTION, **body):
    return client.post(
        URL, data=json.dumps({"text": text, **body}), content_type="application/json"
    )


@pytest.fixture
def real_answer(settings, monkeypatch):
    """The real answer service, the stub retriever, and a scripted fake LLM."""
    settings.USE_STUB_ANSWER = False
    settings.USE_STUB_RETRIEVER = True
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    services._answer_service.cache_clear()
    replies: list = []
    prompts: list[str] = []

    async def fake_generate(system, user, json_mode=True, temperature=0.0):
        prompts.append(user)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(answer_module, "generate", fake_generate)
    yield replies, prompts
    services._answer_service.cache_clear()


def model_reply(status="answered", text="Report the loss early.", cited=(1,)) -> str:
    return json.dumps({"status": status, "answer_text": text, "cited_ids": list(cited)})


def test_valid_json_is_answered_with_the_retrieved_citations(client, real_answer):
    replies, prompts = real_answer
    replies.append(model_reply())
    res = ask(client)
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["status"] == "answered"
    assert body["answer_text"] == "Report the loss early."
    assert body["is_demo"] is False
    # The stub retriever's PMFBY passage, passed to the model as [1] and cited back.
    assert [c["id"] for c in body["citations"]] == ["stub-pmfby-34"]
    assert body["citations"][0]["title"] == "PMFBY Operational Guidelines"
    assert "[1] (PMFBY Operational Guidelines" in prompts[0]
    message = Message.objects.get(pk=body["message_id"])
    assert message.model_name == "fake-model"
    assert message.status == "answered"


def test_a_model_decline_is_declined_with_a_contact(client, real_answer):
    replies, _ = real_answer
    replies.append(model_reply(status="declined", cited=()))
    body = ask(client).json()
    assert body["status"] == "declined"
    assert body["citations"] == []
    assert body["contact"]["label"]


def test_invalid_json_twice_is_declined(client, real_answer):
    replies, _ = real_answer
    replies.extend(["not json", '{"status": "answered"}'])
    body = ask(client).json()
    assert body["status"] == "declined"
    assert body["citations"] == []
    assert not replies, "the service retries once, then declines"


def test_invalid_json_then_valid_json_is_answered(client, real_answer):
    replies, _ = real_answer
    replies.extend(["```json\nnot json\n```", model_reply()])
    assert ask(client).json()["status"] == "answered"


def test_a_citation_out_of_range_is_declined(client, real_answer):
    replies, _ = real_answer
    replies.extend([model_reply(cited=(7,)), model_reply(cited=(0,))])
    body = ask(client).json()
    assert body["status"] == "declined"
    assert body["citations"] == []


def test_a_low_retrieval_score_declines_without_calling_the_model(client, real_answer):
    replies, prompts = real_answer
    body = ask(client, text="asdf").json()  # the stub retriever scores gibberish at 0.12
    assert body["status"] == "declined"
    assert prompts == []


def test_a_provider_error_is_the_standard_502(client, real_answer):
    replies, _ = real_answer
    replies.append(ProviderError("LLM call failed (fake-model at http://llm.test/v1): down"))
    res = ask(client)
    assert res.status_code == 502
    assert res.json() == {
        "code": "provider_error",
        "message": "An upstream service failed. Please try again.",
    }


@pytest.mark.parametrize("language", ["en", "hi", "ta"])
def test_decline_text_is_localised(client, real_answer, language):
    replies, _ = real_answer
    replies.append(model_reply(status="declined", cited=()))
    body = ask(client, language=language).json()
    assert body["status"] == "declined"
    assert body["answer_text"] == DECLINE_TEXT[language]
    assert body["answer_text"] != DECLINE_TEXT["en"] or language == "en"


def test_the_decline_contact_is_never_a_placeholder(client, real_answer):
    replies, _ = real_answer
    replies.append(model_reply(status="declined", cited=()))
    contact = ask(client).json()["contact"]
    for value in contact.values():
        assert "[ADD" not in value and "[" not in value


def test_the_decline_contact_comes_from_settings(client, real_answer, settings):
    replies, _ = real_answer
    settings.HELPLINE_LABEL = "Tamil Nadu cooperative department"
    settings.HELPLINE_DETAIL = "Verified detail from the team"
    services._answer_service.cache_clear()
    replies.append(model_reply(status="declined", cited=()))
    contact = ask(client).json()["contact"]
    assert contact == {
        "label": "Tamil Nadu cooperative department",
        "detail": "Verified detail from the team",
    }
