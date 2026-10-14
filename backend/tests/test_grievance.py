import pytest

from .conftest import post_json

URL = "/api/v1/grievance/guide"
DEPOSIT = "My society has not refunded my fixed deposit after two written requests."


def test_categories(client):
    body = client.get("/api/v1/grievance/categories").json()
    ids = [c["id"] for c in body]
    assert "deposit-refund" in ids and "crop-insurance" in ids
    assert all({"id", "label", "description"} == set(c) for c in body)


def test_guide_detects_category_and_builds_a_draft(client):
    res = post_json(client, URL, {"description": DEPOSIT, "state": "tn", "language": "ta"})
    assert res.status_code == 200
    body = res.json()
    assert body["category"]["id"] == "deposit-refund"
    assert body["forum"] and body["forum_note"]
    assert len(body["steps"]) >= 3 and body["documents_needed"]
    assert DEPOSIT in body["draft_text"]
    assert "TN" in body["draft_text"]
    assert body["is_demo"] is True


def test_category_hint_wins(client):
    body = post_json(
        client, URL, {"description": DEPOSIT, "category_hint": "crop-insurance"}
    ).json()
    assert body["category"]["id"] == "crop-insurance"
    assert "Insurance company" in body["forum"]


@pytest.mark.parametrize(
    "payload",
    [
        {"description": "too short"},
        {"description": DEPOSIT, "language": "fr"},
        {"description": DEPOSIT, "category_hint": "not-a-category"},
        {},
    ],
)
def test_invalid_requests_are_422(client, payload):
    res = post_json(client, URL, payload)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
