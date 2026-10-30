"""Tests for the PMFBY fast path, the speech factory and the warm-up (role C).

Run from backend/:  python -m pytest tests/test_fastpath_factory_warmup.py -v
"""

import asyncio

import pytest
import yaml

from services import warmup
from services.schemes_fastpath import (
    FastPathAnswerService,
    SchemeFastPath,
    load_verified_fact,
)
from services.speech.factory import build_speech_provider
from services.speech.whisper_provider import WhisperSpeechProvider
from services.stubs import StubSpeechProvider

BODY = "Report the loss within 72 hours of the damage."
QUESTION = "My crop is damaged by hailstorm, when should I report the loss?"
HINDI_QUESTION = "फसल का नुकसान हुआ तो कब सूचना देनी है?"


def _scheme(placeholder=False, source="https://pmfby.gov.in/", as_of="2026-10-22", body=BODY):
    return {
        "slug": "pmfby",
        "title": "PMFBY",
        "facts": [
            {
                "id": "loss",
                "kind": "loss-reporting",
                "body": body,
                "source_label": "Operational Guidelines",
                "source_url": source,
                "as_of": as_of,
                "is_placeholder": placeholder,
            }
        ],
    }


def _write(tmp_path, scheme):
    path = tmp_path / "schemes.yaml"
    path.write_text(yaml.safe_dump({"schemes": [scheme]}, allow_unicode=True), encoding="utf-8")
    return path


def _texts(tmp_path, hindi_reviewed=False):
    path = tmp_path / "fastpath_text.yaml"
    data = {"loss": {"hi": {"reviewed": hindi_reviewed, "text": "72 घंटे के भीतर सूचना दें।"}}}
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class _Inner:
    def __init__(self):
        self.called = False

    async def ask(self, text, *, language, state, document_id=None):
        self.called = True
        return "inner"


@pytest.mark.parametrize(
    "scheme",
    [_scheme(placeholder=True), _scheme(source=None), _scheme(as_of=None), _scheme(body="")],
)
def test_placeholder_or_unsourced_fact_is_not_used(tmp_path, scheme):
    assert load_verified_fact(_write(tmp_path, scheme)) is None
    assert not SchemeFastPath.from_files(_write(tmp_path, scheme)).active


def test_the_real_placeholder_layout_is_never_served(tmp_path):
    placeholder = _scheme(placeholder=True, source=None, as_of=None, body="Pending.")
    fast = SchemeFastPath.from_files(_write(tmp_path, placeholder))
    assert fast.answer(QUESTION, "en") is None


def test_matching_question_gets_cited_english_answer(tmp_path):
    fast = SchemeFastPath.from_files(_write(tmp_path, _scheme()))
    answer = fast.answer(QUESTION, "en")
    assert answer.status == "answered"
    assert answer.text == BODY
    assert answer.citations[0].source_url == "https://pmfby.gov.in/"
    assert answer.citations[0].published_date == "2026-10-22"


def test_unrelated_question_does_not_match(tmp_path):
    fast = SchemeFastPath.from_files(_write(tmp_path, _scheme()))
    assert fast.answer("How do I register a cooperative society?", "en") is None


def test_hindi_text_used_only_when_reviewed(tmp_path):
    schemes = _write(tmp_path, _scheme())
    unreviewed = SchemeFastPath.from_files(schemes, _texts(tmp_path, hindi_reviewed=False))
    assert unreviewed.answer(HINDI_QUESTION, "hi").language == "en"
    reviewed = SchemeFastPath.from_files(schemes, _texts(tmp_path, hindi_reviewed=True))
    assert reviewed.answer(HINDI_QUESTION, "hi").language == "hi"


def test_missing_translation_file_falls_back_to_english(tmp_path):
    fast = SchemeFastPath.from_files(_write(tmp_path, _scheme()), tmp_path / "nope.yaml")
    assert fast.answer(HINDI_QUESTION, "hi").language == "en"


def test_service_skips_fast_path_for_document_questions(tmp_path):
    inner = _Inner()
    service = FastPathAnswerService(inner, SchemeFastPath.from_files(_write(tmp_path, _scheme())))
    result = asyncio.run(service.ask(QUESTION, language="en", state=None, document_id="doc-1"))
    assert result == "inner" and inner.called


def test_service_answers_from_fast_path_without_calling_inner(tmp_path):
    inner = _Inner()
    service = FastPathAnswerService(inner, SchemeFastPath.from_files(_write(tmp_path, _scheme())))
    result = asyncio.run(service.ask(QUESTION, language="en", state=None))
    assert result.model == "schemes.yaml" and not inner.called


def test_factory_choices(monkeypatch):
    assert isinstance(build_speech_provider("stub"), StubSpeechProvider)
    assert isinstance(build_speech_provider("Whisper"), WhisperSpeechProvider)
    monkeypatch.setenv("SPEECH_PROVIDER", "whisper")
    assert isinstance(build_speech_provider(), WhisperSpeechProvider)
    monkeypatch.delenv("SPEECH_PROVIDER")
    assert isinstance(build_speech_provider(), StubSpeechProvider)
    with pytest.raises(ValueError):
        build_speech_provider("bhashini")


def test_native_endpoint_strips_v1(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://host.docker.internal:11434/v1")
    assert warmup._native_endpoint() == ("http", "host.docker.internal", 11434, "/api/generate")


def test_warm_up_never_raises(monkeypatch):
    def boom():
        raise RuntimeError("ollama is down")

    async def whisper_ok(languages):
        return None

    monkeypatch.setattr(warmup, "_load_llm_sync", boom)
    monkeypatch.setattr(warmup, "warm_up_whisper", whisper_ok)
    assert asyncio.run(warmup.warm_up_all()) == {"llm": False, "whisper": True}


def test_warm_up_reports_whisper_failure(monkeypatch):
    async def whisper_bad(languages):
        raise RuntimeError("no model")

    monkeypatch.setattr(warmup, "_load_llm_sync", lambda: None)
    monkeypatch.setattr(warmup, "warm_up_whisper", whisper_bad)
    assert asyncio.run(warmup.warm_up_all()) == {"llm": True, "whisper": False}


class _Retriever:
    def __init__(self):
        self.calls = 0

    async def search(self, query, *, state, language, top_k=4, document_id=None):
        self.calls += 1
        return []


def _grounded(tmp_path, with_fast_path=True):
    from services.answer import GroundedAnswerService

    fast = SchemeFastPath.from_files(_write(tmp_path, _scheme())) if with_fast_path else None
    retriever = _Retriever()
    return GroundedAnswerService(retriever, fast_path=fast), retriever


def test_grounded_service_answers_from_the_fast_path_first(tmp_path):
    service, retriever = _grounded(tmp_path)
    result = asyncio.run(service.ask(QUESTION, language="en", state=None))
    assert result.model == "schemes.yaml" and retriever.calls == 0


def test_grounded_service_skips_the_fast_path_for_a_document(tmp_path):
    service, retriever = _grounded(tmp_path)
    result = asyncio.run(service.ask(QUESTION, language="en", state=None, document_id="d1"))
    assert result.status == "declined" and retriever.calls == 1


def test_grounded_service_without_a_fast_path_behaves_as_before(tmp_path):
    service, retriever = _grounded(tmp_path, with_fast_path=False)
    result = asyncio.run(service.ask(QUESTION, language="en", state=None))
    assert result.status == "declined" and retriever.calls == 1
