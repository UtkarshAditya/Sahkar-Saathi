import pytest
from django.contrib.auth import get_user_model

URL = "/api/v1/eval/latest"


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_user("staff", password="pw-for-tests", is_staff=True)
    client.force_login(user)
    return user


def test_anonymous_gets_401(client):
    res = client.get(URL)
    assert res.status_code == 401
    assert res.json()["code"] == "not_authenticated"


def test_non_staff_gets_403(client):
    user = get_user_model().objects.create_user("member", password="pw-for-tests")
    client.force_login(user)
    res = client.get(URL)
    assert res.status_code == 403
    assert res.json()["code"] == "staff_only"


def test_staff_sees_the_summary(client, staff):
    body = client.get(URL).json()
    assert body["is_sample"] is True
    assert {m["key"] for m in body["metrics"]} == {"hit_rate", "faithfulness", "correct_refusal"}
    assert body["latest"]["id"] == body["runs"][-1]["id"]
    assert {"embedding_model", "llm", "top_k", "threshold", "prompt_version"} == set(
        body["latest"]["config"]
    )
