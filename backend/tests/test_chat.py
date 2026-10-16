import json

import pytest

from apps.chat import api as chat_api
from apps.chat.models import Conversation, Message
from config.throttles import CHAT_THROTTLE
from services.types import Answer, Passage

URL = "/api/v1/chat/ask"


def ask(client, **body):
    return client.post(URL, data=json.dumps(body), content_type="application/json")


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_answered_with_citations(client):
    res = ask(client, text="What should I do if my insured crop is damaged under PMFBY?")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "answered"
    assert body["needs_state"] is False
    assert body["is_demo"] is True
    assert body["citations"], "an answered question must cite a passage"
    citation = body["citations"][0]
    assert {"id", "document_id", "title", "publisher", "published_date", "page", "url"} <= set(
        citation
    )
    assert body["conversation_id"] and body["message_id"]


def test_needs_state_when_state_missing(client):
    res = ask(client, text="How are board members of a PACS elected?")
    body = res.json()
    assert body["needs_state"] is True
    assert body["citations"] == []


def test_partial_for_uncovered_state(client):
    res = ask(client, text="How are board members of a PACS elected?", state="up")
    body = res.json()
    assert body["status"] == "partial"
    assert body["needs_state"] is False


def test_regional_language_is_tamil(client):
    assert ask(client, text="PMFBY claim", language="ta").status_code == 200
    assert ask(client, text="PMFBY claim", language="mr").status_code == 422


def test_answered_for_covered_state(client):
    res = ask(client, text="How are board members of a PACS elected?", state="TN")
    assert res.json()["status"] == "answered"


@pytest.mark.parametrize("text", ["asdf", "Will I win my court case?"])
def test_declined_has_contact_and_no_citations(client, text):
    body = ask(client, text=text).json()
    assert body["status"] == "declined"
    assert body["citations"] == []
    assert body["contact"]["label"]


def test_follow_up_reuses_the_conversation(client):
    first = ask(client, text="PMFBY claim").json()
    second = ask(client, text="Which documents?", conversation_id=first["conversation_id"]).json()
    assert second["conversation_id"] == first["conversation_id"]
    assert Conversation.objects.get().messages.count() == 2


def test_unknown_conversation_id_starts_a_new_one(client):
    body = ask(client, text="PMFBY claim", conversation_id="not-a-real-id").json()
    assert body["conversation_id"] != "not-a-real-id"
    assert Conversation.objects.filter(pk=body["conversation_id"]).exists()


def test_answer_is_stored_with_citations_and_metrics(client):
    body = ask(client, text="PMFBY crop damage", language="ta", state="TN").json()
    message = Message.objects.get(pk=body["message_id"])
    assert message.status == "answered"
    assert message.language == "ta" and message.state == "TN"
    assert message.top_score and message.top_score > 0.5
    assert message.model_name == "stub"
    assert message.latency_ms >= 0
    assert message.is_demo
    assert message.question_text == "PMFBY crop damage"
    assert [c.chunk_id for c in message.citations.all()] == [c["id"] for c in body["citations"]]


def test_declined_answer_stores_top_score_but_no_citations(client):
    body = ask(client, text="asdf").json()
    message = Message.objects.get(pk=body["message_id"])
    assert message.status == "declined"
    assert message.top_score is not None and message.top_score < 0.5
    assert message.citations.count() == 0


def test_personal_details_are_scrubbed_before_storing(client):
    body = ask(client, text="PMFBY claim, call me on 98765 43210 or a@b.com").json()
    stored = Message.objects.get(pk=body["message_id"]).question_text
    assert "98765" not in stored and "a@b.com" not in stored
    assert "[phone]" in stored and "[email]" in stored


def test_no_text_is_stored_when_store_messages_is_off(client, settings):
    settings.STORE_MESSAGES = False
    body = ask(client, text="PMFBY claim").json()
    message = Message.objects.get(pk=body["message_id"])
    assert message.question_text == "" and message.answer_text == ""
    assert message.status == "answered", "metrics are still stored"


def test_rate_limit_returns_429_in_the_error_shape(client, monkeypatch):
    monkeypatch.setattr(CHAT_THROTTLE, "num_requests", 2)
    assert ask(client, text="PMFBY claim").status_code == 200
    assert ask(client, text="PMFBY claim").status_code == 200
    res = ask(client, text="PMFBY claim")
    assert res.status_code == 429
    assert res.json()["code"] == "rate_limited"
    assert res.has_header("Retry-After")


def test_health_reports_database(client):
    body = client.get("/api/v1/health").json()
    assert body["database"] == "ok"


@pytest.mark.parametrize(
    "body",
    [
        {"text": "   "},
        {"text": "x" * 1001},
        {"text": "PMFBY", "language": "fr"},
        {},
    ],
)
def test_validation_errors_use_error_shape(client, body):
    res = ask(client, **body)
    assert res.status_code == 422
    assert set(res.json()) == {"code", "message"}
    assert res.json()["code"] == "validation_error"


def test_service_not_ready_without_stubs(client, settings):
    settings.USE_STUBS = False
    res = ask(client, text="PMFBY claim")
    assert res.status_code == 503
    assert res.json()["code"] == "service_not_ready"


def test_citation_with_a_null_published_date_serialises(client, monkeypatch):
    passage = Passage(
        chunk_id="c-1",
        text="A passage from an undated source.",
        document_id="CEN-UNDATED",
        document_title="Undated source",
        publisher="Test",
        source_url=None,
        published_date=None,
        page=None,
        score=0.9,
        state=None,
    )

    class UndatedService:
        async def ask(self, text, *, language, state, document_id=None):
            return Answer(text="Answer.", status="answered", language=language, citations=[passage])

    monkeypatch.setattr(chat_api, "get_answer_service", lambda: UndatedService())
    res = ask(client, text="A question about an undated source")
    assert res.status_code == 200, res.content
    assert res.json()["citations"][0]["published_date"] is None
