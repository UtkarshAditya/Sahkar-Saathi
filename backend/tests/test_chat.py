import json

import pytest

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


def test_answered_for_covered_state(client):
    res = ask(client, text="How are board members of a PACS elected?", state="MH")
    assert res.json()["status"] == "answered"


@pytest.mark.parametrize("text", ["asdf", "Will I win my court case?"])
def test_declined_has_contact_and_no_citations(client, text):
    body = ask(client, text=text).json()
    assert body["status"] == "declined"
    assert body["citations"] == []
    assert body["contact"]["label"]


def test_conversation_id_is_kept(client):
    body = ask(client, text="PMFBY claim", conversation_id="abc123").json()
    assert body["conversation_id"] == "abc123"


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
