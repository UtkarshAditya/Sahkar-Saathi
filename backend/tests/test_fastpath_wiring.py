"""config/services.py wiring: the scheme fast path, the speech factory, and warm_models --llm.

No Ollama, Qdrant, Docker or network: the grounded service's own ask() is replaced by a fake.
"""

import asyncio
import io

import pytest
import yaml
from django.core.management import call_command

from config import services
from services import warmup
from services.schemes_fastpath import FastPathAnswerService
from services.speech.whisper_provider import WhisperSpeechProvider
from services.stubs import StubAnswerService, StubSpeechProvider

LOSS_QUESTION = "My crop is damaged by hailstorm, when should I report the loss?"
OTHER_QUESTION = "How do I register a cooperative society?"


@pytest.fixture
def real_answer(settings):
    """USE_STUB_ANSWER=false over the stub retriever, with a clean cache around the test."""
    settings.USE_STUB_ANSWER = False
    settings.USE_STUB_RETRIEVER = True
    services._answer_service.cache_clear()
    yield settings
    services._answer_service.cache_clear()


def _record_inner(service, monkeypatch):
    """Replace the grounded service's ask(); returns the list of questions it received."""
    asked = []

    async def fake_ask(text, *, language, state, document_id=None):
        asked.append(text)
        return "from the grounded service"

    monkeypatch.setattr(service.inner, "ask", fake_ask)
    return asked


def _ask(service, question, document_id=None):
    return asyncio.run(service.ask(question, language="en", state=None, document_id=document_id))


def test_real_answer_service_is_wrapped_in_the_fast_path(real_answer):
    service = services.get_answer_service()
    assert isinstance(service, FastPathAnswerService)
    assert service.fast_path.active  # the shipped schemes.yaml has a verified "loss" fact


def test_fast_path_answers_a_loss_question_without_the_grounded_service(real_answer, monkeypatch):
    service = services.get_answer_service()
    asked = _record_inner(service, monkeypatch)

    answer = _ask(service, LOSS_QUESTION)

    assert answer.model == "schemes.yaml"
    assert answer.status == "answered" and answer.citations
    assert answer.is_demo is False
    assert asked == []


def test_a_question_the_fast_path_does_not_match_reaches_the_grounded_service(
    real_answer, monkeypatch
):
    service = services.get_answer_service()
    asked = _record_inner(service, monkeypatch)

    assert _ask(service, OTHER_QUESTION) == "from the grounded service"
    assert asked == [OTHER_QUESTION]


def test_a_document_question_skips_the_fast_path(real_answer, monkeypatch):
    service = services.get_answer_service()
    asked = _record_inner(service, monkeypatch)

    _ask(service, LOSS_QUESTION, document_id="doc-1")

    assert asked == [LOSS_QUESTION]


def test_the_stub_answer_service_has_no_fast_path(settings):
    settings.USE_STUB_ANSWER = True
    services._answer_service.cache_clear()
    try:
        assert isinstance(services.get_answer_service(), StubAnswerService)
    finally:
        services._answer_service.cache_clear()


def _content_dir(tmp_path, *, placeholder: bool):
    scheme = {
        "slug": "pmfby",
        "title": "PMFBY",
        "facts": [
            {
                "id": "loss",
                "body": "Pending." if placeholder else "Report the loss within 72 hours.",
                "source_label": "Guidelines",
                "source_url": None if placeholder else "https://pmfby.gov.in/",
                "as_of": None if placeholder else "2026-10-22",
                "is_placeholder": placeholder,
            }
        ],
    }
    (tmp_path / "schemes.yaml").write_text(yaml.safe_dump({"schemes": [scheme]}), encoding="utf-8")
    return tmp_path


def test_a_placeholder_fact_is_never_served(real_answer, monkeypatch, tmp_path):
    real_answer.CONTENT_DIR = _content_dir(tmp_path, placeholder=True)
    service = services.get_answer_service()
    asked = _record_inner(service, monkeypatch)

    result = _ask(service, LOSS_QUESTION)

    assert not service.fast_path.active
    assert result == "from the grounded service" and asked == [LOSS_QUESTION]


def test_an_unreadable_schemes_file_leaves_the_grounded_service_on_its_own(real_answer, tmp_path):
    real_answer.CONTENT_DIR = tmp_path  # no schemes.yaml here
    service = services.get_answer_service()
    assert not isinstance(service, FastPathAnswerService)
    assert hasattr(service, "retriever")  # the plain GroundedAnswerService


@pytest.mark.parametrize(
    ("use_stub", "name", "kind"),
    [(True, "stub", StubSpeechProvider), (False, "whisper", WhisperSpeechProvider)],
)
def test_the_speech_provider_comes_from_the_factory(settings, monkeypatch, use_stub, name, kind):
    from services.speech import factory

    asked = []
    real_build = factory.build_speech_provider

    def spy(chosen=None):
        asked.append(chosen)
        return real_build(chosen)

    monkeypatch.setattr(factory, "build_speech_provider", spy)
    settings.USE_STUB_SPEECH = use_stub
    services._speech_provider.cache_clear()
    try:
        provider = services.get_speech_provider()
    finally:
        services._speech_provider.cache_clear()

    assert asked == [name]
    assert isinstance(provider, kind)
    if not use_stub:
        assert isinstance(provider.synthesizer, StubSpeechProvider)


# --- warm_models and the LLM warm-up ----------------------------------------------------


@pytest.fixture
def llm_loads(settings, monkeypatch):
    """Real answer service, stub speech and retrieval; counts calls to the LLM warm-up."""
    settings.USE_STUB_ANSWER = False
    settings.USE_STUB_SPEECH = True
    settings.USE_STUB_RETRIEVER = True
    settings.WARM_ON_START = False
    calls = []
    monkeypatch.setattr(warmup, "load_llm", lambda: calls.append("llm"))
    return calls


def _warm(*args) -> str:
    out = io.StringIO()
    call_command("warm_models", *args, stdout=out)
    return out.getvalue()


def test_warm_models_does_not_touch_the_llm_by_default(llm_loads):
    assert "nothing to warm" in _warm()
    assert llm_loads == []


def test_warm_models_llm_flag_loads_the_llm(llm_loads):
    assert "language model" in _warm("--llm")
    assert llm_loads == ["llm"]


def test_warm_on_start_loads_the_llm(llm_loads, settings):
    settings.WARM_ON_START = True
    _warm()
    assert llm_loads == ["llm"]


def test_warm_models_ignores_the_llm_flag_with_the_stub_answer(llm_loads, settings):
    settings.USE_STUB_ANSWER = True
    assert "nothing to warm" in _warm("--llm")
    assert llm_loads == []


def test_an_llm_that_is_down_does_not_fail_warm_models(llm_loads, monkeypatch):
    def down():
        raise ConnectionRefusedError("ollama is down")

    monkeypatch.setattr(warmup, "load_llm", down)
    assert "could not load the language model" in _warm("--llm")
