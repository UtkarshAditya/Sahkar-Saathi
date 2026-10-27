"""The forums.yaml-backed grievance guide (USE_STUB_GRIEVANCE=false): details come only from
the YAML, gaps are stated, and nothing is invented. No network."""

import asyncio
import re

import pytest
import yaml

from config import services
from services import grievance
from services.grievance import FORUMS_BY_CATEGORY, Forum, ForumsGrievanceGuide, load_forums
from services.types import Contact

from .conftest import post_json

URL = "/api/v1/grievance/guide"
CROP = "My crop insurance claim was rejected after the flood damaged my fields."
DEPOSIT = "My society has not refunded my fixed deposit after two written requests."
CONTACT = Contact(label="Your district cooperative office", detail="Details to be added.")


@pytest.fixture
def forums():
    return load_forums()


@pytest.fixture
def guide(forums):
    return ForumsGrievanceGuide(forums, CONTACT)


def run(guide, description, **kwargs):
    kwargs.setdefault("state", None)
    kwargs.setdefault("language", "en")
    return asyncio.run(guide.guide(description, **kwargs))


@pytest.fixture
def real_guide(settings):
    settings.USE_STUB_GRIEVANCE = False
    services._grievance_guide.cache_clear()
    yield
    services._grievance_guide.cache_clear()


# --- The data -------------------------------------------------------------------------


def test_forums_yaml_loads_and_every_forum_has_a_source_and_a_date(forums):
    assert forums, "forums.yaml has forums"
    for forum in forums.values():
        assert forum.source_url.startswith("https://") and forum.as_of, forum.id


def test_every_forum_used_by_a_category_exists(forums):
    for category_id, forum_ids in FORUMS_BY_CATEGORY.items():
        assert all(f in forums for f in forum_ids), category_id


def test_a_forum_without_a_source_is_refused(tmp_path):
    path = tmp_path / "forums.yaml"
    path.write_text(
        yaml.safe_dump({"forums": [{"id": "x", "name": "X", "description": "d", "as_of": "2026"}]})
    )
    with pytest.raises(ValueError, match="needs 'source_url'"):
        load_forums(path)


def test_a_forum_without_a_date_is_refused(tmp_path):
    path = tmp_path / "forums.yaml"
    forum = {"id": "x", "name": "X", "description": "d", "source_url": "https://example.org"}
    path.write_text(yaml.safe_dump({"forums": [forum]}))
    with pytest.raises(ValueError, match="needs 'as_of'"):
        load_forums(path)


def test_a_category_that_needs_a_missing_forum_is_refused():
    with pytest.raises(ValueError, match="has no forum"):
        ForumsGrievanceGuide({}, CONTACT)


# --- Categories -----------------------------------------------------------------------


def test_categories_include_every_stub_category_and_an_other_bucket(guide):
    ids = [c.id for c in guide.categories()]
    assert ids == [
        "deposit-refund",
        "membership",
        "election",
        "records",
        "loan",
        "crop-insurance",
        "other",
    ]
    assert all(c.label and c.description for c in guide.categories())


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (DEPOSIT, "deposit-refund"),
        (CROP, "crop-insurance"),
        ("They refused my membership and removed my name from the register.", "membership"),
        ("The board election was held without any notice to members.", "election"),
        ("The secretary will not show me the audit report or the minutes.", "records"),
        ("They are charging extra interest on my loan and sent a recovery notice.", "loan"),
        ("मेरी फसल का बीमा दावा खारिज कर दिया गया है", "crop-insurance"),
        ("எனது பயிர் காப்பீடு கோரிக்கை நிராகரிக்கப்பட்டது", "crop-insurance"),
    ],
)
def test_keyword_detection(guide, text, expected):
    assert run(guide, text).category.id == expected


def test_the_category_with_the_most_matches_wins(guide):
    text = "Crop insurance claim: they also kept my deposit"  # 2 crop words, 1 deposit word
    assert run(guide, text).category.id == "crop-insurance"


def test_nothing_matching_is_other_not_a_guess(guide):
    result = run(guide, "Something happened at the society that I do not understand.")
    assert result.category.id == "other"
    assert result.category.label == "Something else"


def test_a_category_hint_wins_over_the_text(guide):
    assert run(guide, DEPOSIT, category_hint="crop-insurance").category.id == "crop-insurance"
    assert run(guide, CROP, category_hint="other").category.id == "other"


def test_an_unknown_category_hint_is_ignored_by_the_service(guide):
    assert run(guide, DEPOSIT, category_hint="not-a-category").category.id == "deposit-refund"


# --- Content from forums.yaml ---------------------------------------------------------


def test_crop_insurance_uses_the_forums_in_forums_yaml(guide, forums):
    result = run(guide, CROP, state="tn")
    main, tracking, escalation = (forums[f] for f in FORUMS_BY_CATEGORY["crop-insurance"])

    assert result.forum == main.name
    note = result.forum_note
    for detail in (main.contact_number, main.alternative_number, main.whatsapp_bot):
        assert detail in note
    assert f"Source: {main.source_url} (as of {main.as_of})" in note
    assert "No time limit or fee" in note, "a missing detail is stated, not invented"
    assert any(tracking.name in step and tracking.description in step for step in result.steps)
    assert any(escalation.name in step for step in result.steps)
    assert result.draft_text.startswith(f"To,\n{escalation.name}\ntn\n")
    assert result.is_demo is False


def test_contact_details_come_from_the_data_not_the_code():
    custom = {
        "krph_helpline": Forum(
            "krph_helpline", "Test helpline", "d1", "https://example.org/a", "2030-01-01",
            contact_number="000-TEST-1",
        ),
        "ncip_portal_grievance": Forum(
            "ncip_portal_grievance", "Test portal", "d2", "https://example.org/b", "2030-01-02",
            website="https://example.org/portal",
        ),
        "state_agriculture_department": Forum(
            "state_agriculture_department", "Test office", "d3", "https://example.org/c",
            "2030-01-03",
        ),
    }  # fmt: skip
    result = run(ForumsGrievanceGuide(custom, CONTACT), CROP)
    assert result.forum == "Test helpline"
    assert "Helpline: 000-TEST-1." in result.forum_note
    assert "14447" not in result.forum_note and "14447" not in " ".join(result.steps)
    assert "https://example.org/a (as of 2030-01-01)" in result.forum_note
    assert result.draft_text.startswith("To,\nTest office\n")


def test_a_forum_with_no_contact_details_says_so():
    bare = {
        f: Forum(f, f"Forum {f}", f"About {f}.", "https://example.org", "2030-01-01")
        for f in FORUMS_BY_CATEGORY["crop-insurance"]
    }
    note = run(ForumsGrievanceGuide(bare, CONTACT), CROP).forum_note
    assert "No helpline number or website is recorded for this forum." in note


def test_a_category_without_a_recorded_forum_says_so_and_invents_nothing(guide):
    result = run(guide, DEPOSIT)
    assert result.forum == CONTACT.label
    assert "not recorded in our data yet" in result.forum_note
    assert CONTACT.detail in result.forum_note
    assert result.is_demo is True
    everything = " ".join([result.forum, result.forum_note, *result.steps, result.draft_text])
    assert not re.search(r"\d{3,}", everything), "no phone number, amount or deadline"
    assert any("not available in our data yet" in step for step in result.steps)
    assert "[Name of the authority" in result.draft_text


@pytest.mark.parametrize("text", [DEPOSIT, CROP, "Something odd happened here, honestly."])
def test_no_category_invents_a_deadline_or_fee(guide, text):
    result = run(guide, text)
    prose = " ".join([*result.steps, *result.documents_needed])
    assert not re.search(r"\d+\s*(days?|hours?|weeks?|months?)", prose, re.I)
    assert not re.search(r"(₹|rs\.?\s*\d|rupees)", prose, re.I)


# --- The draft ------------------------------------------------------------------------


def test_the_draft_keeps_the_members_words_and_marks_what_they_fill_in(guide):
    result = run(guide, DEPOSIT, state="TN")
    assert DEPOSIT in result.draft_text
    assert "TN" in result.draft_text
    for placeholder in ("[name of cooperative society]", "[Your name]", "[Date]"):
        assert placeholder in result.draft_text
    assert "{" not in result.draft_text and "}" not in result.draft_text


def test_without_a_state_the_draft_asks_for_one(guide):
    assert "[Your state]" in run(guide, DEPOSIT).draft_text


def test_steps_and_documents_are_unique_and_non_empty(guide):
    for category in guide.categories():
        result = run(guide, "x" * 25, category_hint=category.id)
        assert len(result.steps) >= 3 and len(set(result.steps)) == len(result.steps)
        assert len(set(result.documents_needed)) == len(result.documents_needed) >= 3
    first, second = run(guide, DEPOSIT), run(guide, DEPOSIT)
    first.documents_needed.append("changed")
    assert "changed" not in second.documents_needed, "responses do not share one list"


# --- Empty and odd input --------------------------------------------------------------


@pytest.mark.parametrize("description", ["", "   ", "\n\t"])
def test_empty_input_at_the_service_gives_the_other_category_and_a_placeholder(guide, description):
    result = run(guide, description)
    assert result.category.id == "other"
    assert "[Describe the problem in your own words]" in result.draft_text
    assert result.steps and result.documents_needed


# --- Through the API ------------------------------------------------------------------


def test_the_api_serves_the_real_guide(client, real_guide, forums):
    res = post_json(client, URL, {"description": CROP, "state": "tn", "language": "ta"})
    assert res.status_code == 200, res.content
    body = res.json()
    assert set(body) == {
        "category",
        "forum",
        "forum_note",
        "steps",
        "documents_needed",
        "draft_text",
        "is_demo",
    }
    assert body["category"]["id"] == "crop-insurance" and body["is_demo"] is False
    assert body["forum"] == forums["krph_helpline"].name
    assert "TN" in body["draft_text"]


def test_the_api_lists_the_real_categories(client, real_guide):
    body = client.get("/api/v1/grievance/categories").json()
    assert [c["id"] for c in body][-1] == "other"
    assert all(set(c) == {"id", "label", "description"} for c in body)


def test_the_api_rejects_an_unknown_category(client, real_guide):
    res = post_json(client, URL, {"description": DEPOSIT, "category_hint": "not-a-category"})
    assert res.status_code == 422
    assert res.json() == {"code": "validation_error", "message": "category_hint: Unknown category."}


@pytest.mark.parametrize("description", ["", "   ", "too short", "x" * 2001])
def test_the_api_rejects_empty_and_out_of_range_descriptions(client, real_guide, description):
    res = post_json(client, URL, {"description": description})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_the_api_returns_503_when_the_data_cannot_be_used(client, settings, monkeypatch):
    def broken():
        raise OSError("no such file")

    monkeypatch.setattr(grievance, "load_forums", broken)
    settings.USE_STUB_GRIEVANCE = False
    services._grievance_guide.cache_clear()
    try:
        res = post_json(client, URL, {"description": DEPOSIT})
    finally:
        services._grievance_guide.cache_clear()
    assert res.status_code == 503 and res.json()["code"] == "service_not_ready"


def test_the_stub_is_still_the_default(client):
    body = post_json(client, URL, {"description": DEPOSIT}).json()
    assert body["is_demo"] is True and "(sample forum)" in body["forum"]


def test_logs_never_contain_the_description(client, real_guide, caplog):
    secret = "My neighbour Ravi Kumar took my deposit of the society money unfairly."
    with caplog.at_level("INFO"):
        res = post_json(client, URL, {"description": secret})
    assert res.status_code == 200
    assert "Ravi" not in caplog.text and "deposit of the society" not in caplog.text
