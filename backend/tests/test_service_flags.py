"""Per-service stub flags (USE_STUB_RETRIEVER, _ANSWER, _SPEECH, _GRIEVANCE) and the
wiring in config/services.py. No network, no model, no LLM."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import services
from config.settings import env_bool, env_value
from services.answer import GroundedAnswerService
from services.retrieval.qdrant_retriever import QdrantRetriever
from services.speech.whisper_provider import WhisperSpeechProvider
from services.stubs import (
    StubAnswerService,
    StubGrievanceGuide,
    StubRetriever,
    StubSpeechProvider,
)
from services.types import ServiceNotReady

BACKEND = Path(__file__).resolve().parent.parent
FLAGS = ["USE_STUB_RETRIEVER", "USE_STUB_ANSWER", "USE_STUB_SPEECH", "USE_STUB_GRIEVANCE"]


@pytest.fixture
def all_stubs(settings):
    for flag in FLAGS:
        setattr(settings, flag, True)
    return settings


def _kinds() -> dict:
    """Which implementation each getter returns (the grievance guide may raise)."""
    try:
        guide = type(services.get_grievance_guide())
    except ServiceNotReady:
        guide = ServiceNotReady
    return {
        "retriever": type(services.get_retriever()),
        "answer": type(services.get_answer_service()),
        "speech": type(services.get_speech_provider()),
        "grievance": guide,
    }


STUB_KINDS = {
    "retriever": StubRetriever,
    "answer": StubAnswerService,
    "speech": StubSpeechProvider,
    "grievance": StubGrievanceGuide,
}


# --- The env helper -------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_env_value_counts_as_unset(monkeypatch, value):
    monkeypatch.setenv("SAHKAR_TEST_FLAG", value)
    assert env_value("SAHKAR_TEST_FLAG") is None
    assert env_bool("SAHKAR_TEST_FLAG", True) is True
    assert env_bool("SAHKAR_TEST_FLAG", False) is False


def test_env_bool_reads_set_values(monkeypatch):
    monkeypatch.setenv("SAHKAR_TEST_FLAG", "false")
    assert env_bool("SAHKAR_TEST_FLAG", True) is False
    monkeypatch.setenv("SAHKAR_TEST_FLAG", "TRUE")
    assert env_bool("SAHKAR_TEST_FLAG", False) is True
    monkeypatch.delenv("SAHKAR_TEST_FLAG")
    assert env_value("SAHKAR_TEST_FLAG") is None


def _flags_from_settings(**env: str) -> list[str]:
    """Load config.settings in a fresh process with exactly these USE_STUB* variables.
    The others are set to "" (unset), which also stops backend/.env from filling them."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("USE_STUB", "DJANGO_"))}
    env = {**dict.fromkeys(["USE_STUBS", *FLAGS], ""), **env}
    code = f"from config import settings as s; print(*[getattr(s, f) for f in {FLAGS!r}])"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        env={**clean, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.split()


def test_flags_follow_use_stubs_and_empty_values_are_unset():
    # No variables: everything is a stub.
    assert _flags_from_settings() == ["True"] * 4
    # Compose passes empty strings: still USE_STUBS (true by default), never "false".
    assert _flags_from_settings(**dict.fromkeys(FLAGS, "")) == ["True"] * 4
    # USE_STUBS=false turns every service real unless a flag says otherwise.
    assert _flags_from_settings(USE_STUBS="false", USE_STUB_ANSWER="") == ["False"] * 4
    # One flag overrides USE_STUBS for its own service only.
    assert _flags_from_settings(USE_STUB_ANSWER="false") == ["True", "False", "True", "True"]


# --- The wiring -----------------------------------------------------------------------


def test_every_service_defaults_to_its_stub(all_stubs):
    assert _kinds() == STUB_KINDS


@pytest.mark.parametrize(
    ("flag", "service", "real"),
    [
        ("USE_STUB_RETRIEVER", "retriever", QdrantRetriever),
        ("USE_STUB_ANSWER", "answer", GroundedAnswerService),
        ("USE_STUB_SPEECH", "speech", WhisperSpeechProvider),
        ("USE_STUB_GRIEVANCE", "grievance", ServiceNotReady),
    ],
)
def test_each_flag_flips_only_its_own_service(all_stubs, flag, service, real):
    setattr(all_stubs, flag, False)
    assert _kinds() == {**STUB_KINDS, service: real}


def test_mixed_mode_real_answer_over_the_stub_retriever(all_stubs):
    all_stubs.USE_STUB_ANSWER = False
    answer = services.get_answer_service()
    assert isinstance(answer, GroundedAnswerService)
    assert isinstance(answer.retriever, StubRetriever)
    assert answer.top_k == all_stubs.TOP_K and answer.min_score == all_stubs.SCORE_THRESHOLD

    # Flipping the retriever flag alone rebuilds the answer service around the real one.
    all_stubs.USE_STUB_RETRIEVER = False
    assert isinstance(services.get_answer_service().retriever, QdrantRetriever)


def test_real_speech_keeps_stub_synthesis_and_loads_no_model(all_stubs, monkeypatch):
    monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
    services._speech_provider.cache_clear()
    all_stubs.USE_STUB_SPEECH = False
    provider = services.get_speech_provider()
    assert isinstance(provider.synthesizer, StubSpeechProvider)
    assert "faster_whisper" not in sys.modules, "the model must load lazily, not at build time"
    services._speech_provider.cache_clear()


def test_not_ready_messages_name_the_flag(all_stubs):
    all_stubs.USE_STUB_GRIEVANCE = False
    with pytest.raises(ServiceNotReady, match="USE_STUB_GRIEVANCE=true"):
        services.get_grievance_guide()


@patch("services.retrieval.qdrant_retriever.QdrantClient")
@patch("services.retrieval.qdrant_retriever.SentenceTransformer")
def test_qdrant_retriever_search_mocked(mock_sentence_transformer, mock_qdrant_client):
    """Verify QdrantRetriever executes successfully with mocked dependencies."""
    mock_model_instance = MagicMock()
    mock_model_instance.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2, 0.3])
    mock_sentence_transformer.return_value = mock_model_instance

    mock_client_instance = MagicMock()
    mock_point = MagicMock()
    mock_point.id = "mock-uuid-1"
    mock_point.score = 0.92
    mock_point.payload = {
        "text": "passage: mock text content",
        "doc_id": "CEN-MSCS-ACT-2002",
        "document_title": "MSCS Act 2002",
        "publisher": "Govt of India",
        "source_url": "https://example.com/act.pdf",
        "published_date": "2025-06-27",
        "page": 1,
        "state": "central",
    }
    mock_client_instance.query_points.return_value = MagicMock(points=[mock_point])
    mock_qdrant_client.return_value = mock_client_instance

    retriever = QdrantRetriever()
    results = asyncio.run(
        retriever.search("cooperative societies", state="TN", language="en", top_k=2)
    )

    assert isinstance(results, list)
    assert len(results) == 1
    passage = results[0]
    assert passage.chunk_id == "mock-uuid-1"
    assert passage.document_id == "CEN-MSCS-ACT-2002"
    assert passage.document_title == "MSCS Act 2002"
    assert passage.publisher == "Govt of India"
    assert passage.source_url == "https://example.com/act.pdf"
    assert passage.published_date == "2025-06-27"
    assert passage.page == 1
    assert passage.state == "central"
    assert passage.score == 0.92
    assert passage.text == "passage: mock text content"

    # Verify query prefix "query: "
    mock_model_instance.encode.assert_called_once_with("query: cooperative societies")

    # Verify query_points call
    mock_client_instance.query_points.assert_called_once()
    call_kwargs = mock_client_instance.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == "sahkar_saathi_chunks"
    assert call_kwargs["query"] == [0.1, 0.2, 0.3]
    assert call_kwargs["limit"] == 2

    # Also test state=None fallback to central
    mock_model_instance.encode.reset_mock()
    mock_client_instance.query_points.reset_mock()
    results_central = asyncio.run(retriever.search("rules", state=None, top_k=1))
    assert len(results_central) == 1
    mock_model_instance.encode.assert_called_once_with("query: rules")
    mock_client_instance.query_points.assert_called_once()
