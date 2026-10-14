"""Schemes and lessons: the endpoints, and the validation rules on the content files."""

import pytest
from pydantic import ValidationError

from apps.lessons.content import load_lessons
from apps.lessons.schemas import QuizQuestionOut
from apps.schemes.content import load_schemes
from apps.schemes.schemas import SchemeFactOut, SchemeOut


def test_content_files_are_valid():
    load_schemes.cache_clear()
    load_lessons.cache_clear()
    assert "pmfby" in load_schemes()
    assert len(load_lessons("en").quiz) == 3


def test_list_schemes(client):
    body = client.get("/api/v1/schemes").json()
    assert {s["slug"] for s in body} >= {"pmfby", "kisan-credit-card"}
    assert "facts" not in body[0]
    assert all(s["source_label"] and s["as_of"] for s in body)


def test_filter_schemes_by_category(client):
    body = client.get("/api/v1/schemes?category=credit").json()
    assert [s["slug"] for s in body] == ["kisan-credit-card"]


def test_pmfby_has_guide_facts(client):
    body = client.get("/api/v1/schemes/pmfby").json()
    kinds = {f["kind"] for f in body["facts"]}
    assert kinds == {"eligibility", "premium", "enrolment", "loss-reporting", "official-info"}
    assert all(f["is_placeholder"] for f in body["facts"]), "no unverified figures"


def test_unknown_scheme_is_404(client):
    res = client.get("/api/v1/schemes/nope")
    assert res.status_code == 404
    assert res.json()["code"] == "scheme_not_found"


def test_verified_scheme_must_have_a_source_url():
    with pytest.raises(ValidationError, match="needs a source_url"):
        SchemeOut(
            slug="x",
            title="X",
            category="credit",
            summary="s",
            eligibility="e",
            how_to_access="h",
            source_label="Official page",
            source_url=None,
            as_of="2026-10-01",
            is_sample=False,
        )


def test_verified_fact_must_have_source_and_date():
    with pytest.raises(ValidationError, match="needs source_url and as_of"):
        SchemeFactOut(
            id="premium",
            kind="premium",
            title="Premium",
            body="2%",
            source_label="Guidelines",
            source_url="https://example.org",
            as_of=None,
            is_placeholder=False,
        )


def test_lessons_and_quiz(client):
    body = client.get("/api/v1/lessons").json()
    assert body["language"] == "en"
    assert {lesson["slug"] for lesson in body["lessons"]} == {
        "loans-and-interest",
        "kcc-basics",
        "savings",
        "spotting-fraud",
    }
    assert len(body["quiz"]) == 3


def test_lessons_fall_back_to_english(client):
    body = client.get("/api/v1/lessons?language=ta").json()
    assert body["language"] == "en"


def test_lessons_reject_unknown_language(client):
    res = client.get("/api/v1/lessons?language=fr")
    assert res.status_code == 422


def test_quiz_answer_index_must_exist():
    with pytest.raises(ValidationError, match="out of range"):
        QuizQuestionOut(id="q", question="?", options=["a", "b"], correct_index=2, explanation="")
