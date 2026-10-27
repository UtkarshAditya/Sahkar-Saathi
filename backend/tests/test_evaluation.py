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


PASSWORD = "pw-for-tests"


def test_the_401_and_403_bodies_are_exactly_the_contract_shape(client):
    anonymous = client.get(URL)
    assert anonymous.status_code == 401
    assert anonymous.json() == {
        "code": "not_authenticated",
        "message": "Log in as staff at /admin/ first.",
    }

    user = get_user_model().objects.create_user("member", password=PASSWORD)
    client.force_login(user)
    non_staff = client.get(URL)
    assert non_staff.status_code == 403
    assert non_staff.json() == {"code": "staff_only", "message": "This page is for staff only."}


def test_staff_logging_in_through_the_admin_login_page_reaches_the_dashboard(client):
    """The Quality page links to this login URL; it must set the session the API checks."""
    get_user_model().objects.create_user("staff", password=PASSWORD, is_staff=True)
    assert client.get(URL).status_code == 401

    login = client.post(
        "/admin/login/?next=/staff/quality",
        {"username": "staff", "password": PASSWORD, "next": "/staff/quality"},
    )
    assert login.status_code == 302 and login["Location"] == "/staff/quality"
    assert client.get(URL).status_code == 200


def test_a_user_without_staff_status_cannot_log_in_to_the_admin_site(client):
    get_user_model().objects.create_user("member", password=PASSWORD)
    login = client.post("/admin/login/", {"username": "member", "password": PASSWORD})
    assert login.status_code == 200, "the admin login form is shown again, with an error"
    assert client.get(URL).status_code == 401, "no session was created"


def test_a_non_staff_session_is_forbidden_not_unauthenticated(client):
    get_user_model().objects.create_user("member", password=PASSWORD)
    assert client.login(username="member", password=PASSWORD)
    assert client.get(URL).status_code == 403


def test_logging_out_ends_access(client, staff):
    assert client.get(URL).status_code == 200
    client.logout()
    assert client.get(URL).status_code == 401


def test_a_deactivated_staff_account_loses_access_at_once(client, staff):
    assert client.get(URL).status_code == 200
    staff.is_active = False
    staff.save()
    res = client.get(URL)
    assert res.status_code == 401 and res.json()["code"] == "not_authenticated"


def test_a_staff_account_that_loses_staff_status_is_forbidden(client, staff):
    staff.is_staff = False
    staff.save()
    res = client.get(URL)
    assert res.status_code == 403 and res.json()["code"] == "staff_only"


def test_a_superuser_who_is_not_staff_flagged_still_needs_is_staff(client):
    user = get_user_model().objects.create_user("odd", password=PASSWORD, is_superuser=True)
    client.force_login(user)
    assert client.get(URL).status_code == 403


def test_no_data_is_sent_with_the_errors(client):
    from apps.evaluation.models import EvalRun

    EvalRun.objects.create(
        label="Secret run", embedding_model="e", top_k=4, threshold=0.5, question_count=1
    )
    assert b"Secret" not in client.get(URL).content
    assert b"run-" not in client.get(URL).content


def test_staff_sees_the_summary(client, staff):
    body = client.get(URL).json()
    assert body["is_sample"] is True
    assert {m["key"] for m in body["metrics"]} == {"hit_rate", "faithfulness", "correct_refusal"}
    assert body["latest"]["id"] == body["runs"][-1]["id"]
    assert {"embedding_model", "llm", "top_k", "threshold", "prompt_version"} == set(
        body["latest"]["config"]
    )
