import pytest

from apps.feedback.models import Feedback

from .conftest import post_json

URL = "/api/v1/feedback"


@pytest.fixture
def message_id(client):
    return post_json(client, "/api/v1/chat/ask", {"text": "PMFBY claim"}).json()["message_id"]


def test_thumbs_up_on_an_answer(client, message_id):
    res = post_json(client, URL, {"message_id": message_id, "rating": "up"})
    assert res.status_code == 201
    assert res.json()["ok"] is True
    feedback = Feedback.objects.get(pk=res.json()["id"])
    assert feedback.rating == "up"
    assert feedback.message_id.hex == message_id


def test_thumbs_down_with_reason(client, message_id):
    res = post_json(
        client, URL, {"message_id": message_id, "rating": "down", "reason": "Wrong state"}
    )
    assert res.status_code == 201
    assert Feedback.objects.get().reason == "Wrong state"


def test_general_comment_without_message(client):
    res = post_json(client, URL, {"comment": "Please add more state documents.", "reason": "Idea"})
    assert res.status_code == 201
    assert Feedback.objects.get().message is None


def test_comment_is_scrubbed(client):
    post_json(client, URL, {"comment": "My Aadhaar is 1234 5678 9012"})
    assert Feedback.objects.get().comment == "My Aadhaar is [aadhaar]"


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "0" * 32])
def test_unknown_message_is_404(client, bad_id):
    res = post_json(client, URL, {"message_id": bad_id, "rating": "up"})
    assert res.status_code == 404
    assert res.json() == {"code": "message_not_found", "message": "That answer was not found."}


@pytest.mark.parametrize(
    "body",
    [
        {},  # neither rating nor comment
        {"rating": "up"},  # rating without the answer it rates
        {"message_id": "x", "rating": "sideways"},
        {"comment": "x" * 1001},
    ],
)
def test_invalid_feedback_is_422(client, body):
    res = post_json(client, URL, body)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
