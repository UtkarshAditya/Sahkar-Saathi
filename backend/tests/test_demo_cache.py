"""DEMO_CACHE: saved answers for the scripted demo questions, and the fallback when a live
service fails on one of them. No network, no model, no LLM."""

import json
from pathlib import Path

import pytest
from django.conf import settings as django_settings

from apps.chat import api as chat_api
from apps.chat import demo_cache
from apps.chat.models import Message
from services.types import Answer, ProviderError, ServiceNotReady

URL = "/api/v1/chat/ask"
SCRIPTED = "What should I do if my insured crop is damaged under PMFBY?"
CONVERSATIONS = Path(django_settings.BASE_DIR).parent / "data" / "eval" / "conversations.json"
RESPONSE_KEYS = {
    "conversation_id",
    "message_id",
    "answer_text",
    "status",
    "needs_state",
    "citations",
    "followups",
    "contact",
    "is_demo",
}


def ask(client, text=SCRIPTED, **body):
    return client.post(
        URL, data=json.dumps({"text": text, **body}), content_type="application/json"
    )


class FailingService:
    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    async def ask(self, text, *, language, state, document_id=None):
        self.calls += 1
        raise self.error


class LiveService:
    """A stand-in for the live service that records how often it is used."""

    def __init__(self):
        self.calls = 0

    async def ask(self, text, *, language, state, document_id=None):
        self.calls += 1
        return Answer(text="Live answer.", status="partial", language=language, is_demo=False)


@pytest.fixture
def demo_on(settings):
    settings.DEMO_CACHE = True
    return settings


def use_service(monkeypatch, service):
    monkeypatch.setattr(chat_api, "get_answer_service", lambda: service)
    return service


# --- Hit ------------------------------------------------------------------------------


def test_a_scripted_question_gets_its_saved_answer(client, demo_on, monkeypatch):
    live = use_service(monkeypatch, LiveService())
    res = ask(client)
    assert res.status_code == 200, res.content
    body = res.json()
    assert set(body) == RESPONSE_KEYS, "the same response shape as a normal answer"
    assert body["status"] == "answered" and body["is_demo"] is True
    assert "72 hours" in body["answer_text"]
    assert [c["id"] for c in body["citations"]] == ["demo-pmfby-loss-reporting"]
    assert body["citations"][0]["url"] == "https://pmfby.gov.in/"
    assert body["citations"][0]["published_date"] is None
    assert live.calls == 0, "a hit does not call the live service"
    message = Message.objects.get(pk=body["message_id"])
    assert message.model_name == demo_cache.MODEL_NAME and message.is_demo is True
    assert message.citations.count() == 1


@pytest.mark.parametrize(
    "text",
    [
        "what should i do if my insured crop is damaged under pmfby",
        "  WHAT   should I do if my   insured crop is damaged under PMFBY??  ",
        "What should I do, if my insured crop is damaged under PMFBY?!",
        "What should I do if my insured crop is damaged under PMFBY?\n",
    ],
)
def test_matching_ignores_case_spacing_and_punctuation(client, demo_on, monkeypatch, text):
    use_service(monkeypatch, LiveService())
    assert ask(client, text).json()["answer_text"].startswith("Report the loss")


@pytest.mark.parametrize(
    ("question", "language", "marker"),
    [
        ("अगर पीएमएफबीवाई के तहत मेरी बीमित फसल खराब हो जाए तो मुझे क्या करना चाहिए?", "hi", "72"),
        (
            "பிஎம்எஃப்பிஒய் திட்டத்தின் கீழ் காப்பீடு செய்யப்பட்ட என் பயிர் சேதமடைந்தால் நான் என்ன செய்ய வேண்டும்?",
            "ta",
            "72",
        ),
    ],
)
def test_hindi_and_tamil_questions_match(client, demo_on, monkeypatch, question, language, marker):
    use_service(monkeypatch, LiveService())
    body = ask(client, question, language=language).json()
    assert body["status"] == "answered" and marker in body["answer_text"]
    assert body["citations"] and body["is_demo"] is True


def test_a_declined_saved_answer_has_no_citations_and_a_contact(client, demo_on, settings):
    settings.HELPLINE_LABEL = "District office"
    settings.HELPLINE_DETAIL = "Details from the team"
    body = ask(client, "Who will win the next election?").json()
    assert body["status"] == "declined" and body["citations"] == []
    assert body["contact"] == {"label": "District office", "detail": "Details from the team"}
    assert body["is_demo"] is True
    deposit = ask(client, "My cooperative society is refusing to return my deposit. What can I do?")
    assert deposit.json()["status"] == "declined" and deposit.json()["contact"]


def test_follow_up_turns_keep_the_conversation(client, demo_on):
    first = ask(client).json()
    second = ask(
        client,
        "Who will win the next election?",
        conversation_id=first["conversation_id"],
    ).json()
    assert second["conversation_id"] == first["conversation_id"]


# --- Miss -----------------------------------------------------------------------------


def test_a_question_that_is_not_scripted_goes_through_the_service(client, demo_on, monkeypatch):
    live = use_service(monkeypatch, LiveService())
    body = ask(client, "How do I renew my ration card?").json()
    assert body["answer_text"] == "Live answer." and body["is_demo"] is False
    assert live.calls == 1


def test_a_question_that_is_not_scripted_works_with_the_stubs(client, demo_on):
    res = ask(client, "asdf")
    assert res.status_code == 200 and res.json()["status"] == "declined"


# --- Flag off -------------------------------------------------------------------------


def test_with_the_flag_off_the_saved_answers_are_never_used(client, settings, monkeypatch):
    settings.DEMO_CACHE = False
    live = use_service(monkeypatch, LiveService())
    body = ask(client).json()
    assert body["answer_text"] == "Live answer." and live.calls == 1


def test_with_the_flag_off_a_failure_is_still_an_error(client, settings, monkeypatch):
    settings.DEMO_CACHE = False
    use_service(monkeypatch, FailingService(ProviderError("LLM call failed")))
    res = ask(client)
    assert res.status_code == 502 and res.json()["code"] == "provider_error"


def test_the_flag_defaults_to_off():
    assert django_settings.DEMO_CACHE is False


# --- Fallback -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ProviderError("LLM call failed"),
        ServiceNotReady("The retriever is unavailable."),
        ConnectionError("vector store down"),  # not wrapped by the retriever yet
    ],
)
def test_a_failing_service_falls_back_to_the_saved_answer(client, demo_on, monkeypatch, error):
    # With a document selected the saved answer is not tried first, so the live service runs,
    # fails, and the saved answer replaces the error.
    failing = use_service(monkeypatch, FailingService(error))
    res = ask(client, document_id="doc-tn-act")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["is_demo"] is True and body["citations"] and "72 hours" in body["answer_text"]
    assert failing.calls == 1


def test_a_failure_on_an_unscripted_question_is_still_an_error(client, demo_on, monkeypatch):
    use_service(monkeypatch, FailingService(ProviderError("LLM call failed")))
    res = ask(client, "How do I renew my ration card?")
    assert res.status_code == 502
    assert res.json() == {
        "code": "provider_error",
        "message": "An upstream service failed. Please try again.",
    }
    use_service(monkeypatch, FailingService(ServiceNotReady("The retriever is unavailable.")))
    assert ask(client, "How do I renew my ration card?").status_code == 503


def test_a_selected_document_skips_the_saved_answer_when_the_service_works(
    client, demo_on, monkeypatch
):
    live = use_service(monkeypatch, LiveService())
    body = ask(client, document_id="doc-tn-act").json()
    assert body["answer_text"] == "Live answer." and live.calls == 1


# --- The data file --------------------------------------------------------------------


def scripted_questions() -> list[tuple[str, str]]:
    conversations = json.loads(CONVERSATIONS.read_text(encoding="utf-8"))
    return [(c["id"], t["text"]) for c in conversations for t in c["turns"]]


def test_every_scripted_question_has_a_saved_answer():
    saved = demo_cache.load_saved_answers()
    questions = scripted_questions()
    assert len(questions) == 6, "five conversations, six turns"
    for conversation, text in questions:
        entry = saved.get(demo_cache.normalise(text))
        assert entry is not None, f"{conversation}: no saved answer for {text!r}"
        assert entry.conversation == conversation
    assert len(saved) == len(questions), "no saved answer without a scripted question"


def test_saved_answers_match_what_the_acceptance_file_expects():
    conversations = json.loads(CONVERSATIONS.read_text(encoding="utf-8"))
    saved = demo_cache.load_saved_answers()
    for conversation in conversations:
        for turn in conversation["turns"]:
            entry = saved[demo_cache.normalise(turn["text"])]
            if turn.get("status") is not None:
                assert entry.status == turn["status"], conversation["id"]
            if turn.get("citations") is True:
                assert entry.citations, conversation["id"]
            if turn.get("citations") is False:
                assert not entry.citations, conversation["id"]
            for needle in turn.get("must_contain") or []:
                assert needle in entry.answer_text, conversation["id"]
            assert entry.language == turn["language"]


def test_nothing_is_invented_in_the_saved_answers():
    for entry in demo_cache.load_saved_answers().values():
        assert entry.source, entry.id
        if entry.status != "declined" and not entry.is_placeholder:
            assert entry.as_of, f"{entry.id}: verified content needs a date"
        if entry.is_placeholder and entry.status != "declined":
            assert "placeholder" in entry.answer_text.lower(), entry.id
        for citation in entry.citations:
            if citation.url:
                assert citation.url == "https://pmfby.gov.in/", "links come from the data files"
        if entry.language != "en":
            assert entry.needs_review, f"{entry.id}: machine-written text must be flagged"


def test_the_pmfby_answer_matches_the_verified_scheme_data():
    """The 72-hour rule and the reporting channels come from schemes.yaml, not from memory."""
    import yaml

    path = Path(django_settings.BASE_DIR) / "services" / "data" / "schemes.yaml"
    pmfby = next(s for s in yaml.safe_load(path.read_text(encoding="utf-8"))["schemes"])
    rule = pmfby["loss_reporting_rule"]
    entry = demo_cache.lookup(SCRIPTED)
    citation = entry.citations[0]
    assert citation.text == rule["timeline"]
    assert citation.source_url == pmfby["source_url"]
    assert citation.document_title == pmfby["document_source"]
    assert "72 hours" in rule["timeline"] and "72 hours" in entry.text


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Hello,   World!", "hello world"),
        ("what's this?", "WHAT'S   THIS"),
        ("क्या है?", "क्या  है"),
        ("a\tb\nc", "a b c"),
    ],
)
def test_normalise(a, b):
    assert demo_cache.normalise(a) == demo_cache.normalise(b)


def test_normalise_keeps_combining_marks_so_different_words_stay_different():
    assert demo_cache.normalise("कि") != demo_cache.normalise("क")


def test_lookup_returns_none_for_anything_else():
    assert demo_cache.lookup("Something else entirely") is None
    assert demo_cache.lookup("") is None
