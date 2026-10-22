"""The speech endpoints with real speech-to-text (USE_STUB_SPEECH=false, a fake Whisper
model), the Tamil stub transcript, and the warm_models command. No model download."""

import io
import sys
import types

import pytest
from django.core.management import call_command

from config import services
from services.speech import whisper_provider


def upload(client, hint="hi"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    audio = SimpleUploadedFile("q.webm", b"fake-webm-bytes", content_type="audio/webm")
    return client.post("/api/v1/speech/transcribe", {"audio": audio, "language_hint": hint})


@pytest.fixture
def real_speech(settings, monkeypatch):
    """USE_STUB_SPEECH=false with faster-whisper replaced by a fake model."""

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_file, **kwargs):
            segment = types.SimpleNamespace(text=" fake transcript ", avg_logprob=-0.1)
            return iter([segment]), types.SimpleNamespace(language=kwargs["language"] or "en")

    module = types.ModuleType("faster_whisper")
    module.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(whisper_provider, "_model", None)
    settings.USE_STUB_SPEECH = False
    services._speech_provider.cache_clear()
    yield settings
    services._speech_provider.cache_clear()


def test_transcribe_uses_whisper_when_the_stub_is_off(client, real_speech):
    res = upload(client, hint="hi")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["text"] == "fake transcript"
    assert body["language"] == "hi"
    assert body["is_demo"] is False


def test_synthesize_still_returns_wav_when_the_stub_is_off(client, real_speech):
    res = client.post(
        "/api/v1/speech/synthesize",
        data='{"text": "Report the loss early.", "language": "en"}',
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res["Content-Type"] == "audio/wav"
    assert res.content[:4] == b"RIFF"


def test_tamil_stub_transcript(client, settings):
    settings.USE_STUB_SPEECH = True
    body = upload(client, hint="ta").json()
    assert body["language"] == "ta"
    assert body["is_demo"] is True
    assert body["text"] and any("஀" <= ch <= "௿" for ch in body["text"])


def _warm() -> str:
    out = io.StringIO()
    call_command("warm_models", stdout=out)
    return out.getvalue()


def test_warm_models_has_nothing_to_warm_with_the_stub(settings):
    settings.USE_STUB_SPEECH = True
    assert "nothing to warm" in _warm()


def test_warm_models_loads_the_model(real_speech):
    out = _warm()
    assert "loaded in" in out
    assert whisper_provider._model is not None


def test_warm_models_never_raises(settings, monkeypatch):
    settings.USE_STUB_SPEECH = False

    def no_network():
        raise OSError("no network")

    monkeypatch.setattr(whisper_provider, "_get_model", no_network)
    out = _warm()
    assert "could not load the Whisper model" in out and "no network" in out
