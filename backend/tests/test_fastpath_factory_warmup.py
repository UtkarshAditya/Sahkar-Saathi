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
    load_verified_facts,
)
from services.speech.factory import build_speech_provider
from services.speech.whisper_provider import WhisperSpeechProvider
from services.stubs import StubSpeechProvider


def _entry(
    verified=True, source="https://pmfby.gov.in/guidelines", as_of="2026-10-29", hi_ok=False
):
    return {
        "slug": "pmfby",
        "title": "PMFBY",
        "facts": [
            {
                "id": "loss-report-window",
                "value": "Report the loss within 72 hours.",
                "source_url": source,
                "as_of": as_of,
                "page": 12,
                "verified": verified,
                "answer": {"en": "Report within 72 hours.", "hi": "72 घंटे में बताएं।"},
                "answer_reviewed": {"hi": hi_ok, "ta": False},
            }
        ],
    }


def _write(tmp_path, entry):
    path = tmp_path / "schemes.yaml"
    path.write_text(yaml.safe_dump([entry], allow_unicode=True), encoding="utf-8")
    return path


class _Inner:
    def __init__(self):
        self.called = False

    async def ask(self, text, *, language, state, document_id=None):
        self.called = True
        return "inner"


def test_unverified_or_unsourced_facts_are_not_loaded(tmp_path):
    assert load_verified_facts(_write(tmp_path, _entry(verified=False))) == []
    assert load_verified_facts(_write(tmp_path, _entry(source="TODO"))) == []
    assert load_verified_facts(_write(tmp_path, _entry(as_of="TODO"))) == []
    assert len(load_verified_facts(_write(tmp_path, _entry()))) == 1


def test_matching_question_gets_cited_english_answer(tmp_path):
    fast = SchemeFastPath.from_file(_write(tmp_path, _entry()))
    answer = fast.answer("My crop is damaged by hailstorm, when should I report the loss?", "en")
    assert answer.status == "answered"
    assert answer.text == "Report within 72 hours."
    assert answer.citations[0].source_url == "https://pmfby.gov.in/guidelines"


def test_unrelated_question_does_not_match(tmp_path):
    fast = SchemeFastPath.from_file(_write(tmp_path, _entry()))
    assert fast.answer("How do I register a cooperative society?", "en") is None


def test_hindi_text_used_only_when_reviewed(tmp_path):
    question = "फसल का नुकसान हुआ तो कब सूचना देनी है?"
    unreviewed = SchemeFastPath.from_file(_write(tmp_path, _entry(hi_ok=False)))
    assert unreviewed.answer(question, "hi").language == "en"
    reviewed = SchemeFastPath.from_file(_write(tmp_path, _entry(hi_ok=True)))
    assert reviewed.answer(question, "hi").language == "hi"


def test_no_english_fallback_means_fall_through(tmp_path):
    path = _write(tmp_path, _entry(hi_ok=False))
    fast = SchemeFastPath(load_verified_facts(path), fallback_to_english=False)
    assert fast.answer("फसल का नुकसान हुआ तो कब सूचना देनी है?", "hi") is None


def test_service_skips_fast_path_for_document_questions(tmp_path):
    fast = SchemeFastPath.from_file(_write(tmp_path, _entry()))
    inner = _Inner()
    service = FastPathAnswerService(inner, fast)
    question = "crop damage, when to report the loss?"
    result = asyncio.run(service.ask(question, language="en", state=None, document_id="doc-1"))
    assert result == "inner" and inner.called


def test_service_answers_from_fast_path_without_calling_inner(tmp_path):
    fast = SchemeFastPath.from_file(_write(tmp_path, _entry()))
    inner = _Inner()
    service = FastPathAnswerService(inner, fast)
    question = "crop damage, when to report the loss?"
    result = asyncio.run(service.ask(question, language="en", state=None))
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
