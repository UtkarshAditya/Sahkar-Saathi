"""Tests for the Whisper speech provider and the audio helper (role C).

They use a fake Whisper model, so they need no model download and no internet.
Run from backend/:  python -m pytest tests/test_speech_provider.py -v
"""

import asyncio
import io
import shutil
import sys
import types
import wave

import pytest

from services.speech import whisper_provider
from services.speech.audio import to_wav_16k_mono
from services.speech.whisper_provider import WhisperSpeechProvider
from services.types import ProviderError, ServiceNotReady


@pytest.fixture
def fake_whisper(monkeypatch):
    """Replace faster-whisper with a fake model and return the list of calls it received."""
    calls = []

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_file, **kwargs):
            calls.append(kwargs)
            audio_file.read()
            segments = [
                types.SimpleNamespace(text=" नमस्ते ", avg_logprob=-0.2),
                types.SimpleNamespace(text="दुनिया", avg_logprob=-0.4),
            ]
            return iter(segments), types.SimpleNamespace(language="hi")

    module = types.ModuleType("faster_whisper")
    module.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(whisper_provider, "_model", None)  # force a fresh "load"
    return calls


def _transcribe(audio=b"abc", hint="hi"):
    provider = WhisperSpeechProvider()
    return asyncio.run(provider.transcribe(audio, content_type="audio/webm", language_hint=hint))


def test_transcribe_returns_text_language_and_confidence(fake_whisper):
    result = _transcribe()
    assert result.text == "नमस्ते दुनिया"
    assert result.language == "hi"
    assert 0.0 <= result.confidence <= 1.0
    assert result.is_demo is False


def test_supported_language_hint_is_passed_to_whisper(fake_whisper):
    _transcribe(hint="ta")
    assert fake_whisper[-1]["language"] == "ta"


def test_unsupported_language_hint_falls_back_to_auto_detect(fake_whisper):
    _transcribe(hint="xx")
    assert fake_whisper[-1]["language"] is None


def test_empty_audio_raises_provider_error(fake_whisper):
    with pytest.raises(ProviderError):
        _transcribe(audio=b"")


def test_model_failure_becomes_provider_error(fake_whisper, monkeypatch):
    def boom(audio, language):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(whisper_provider, "_transcribe_sync", boom)
    with pytest.raises(ProviderError):
        _transcribe()


def test_synthesize_without_a_synthesizer_is_not_ready():
    with pytest.raises(ServiceNotReady):
        asyncio.run(WhisperSpeechProvider().synthesize("hello", language="en"))


def test_synthesize_delegates_to_the_given_synthesizer():
    class FakeSynth:
        async def synthesize(self, text, *, language):
            return b"WAV-BYTES"

    provider = WhisperSpeechProvider(synthesizer=FakeSynth())
    assert asyncio.run(provider.synthesize("hello", language="en")) == b"WAV-BYTES"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_audio_is_converted_to_16khz_mono_wav():
    source = io.BytesIO()
    with wave.open(source, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x01" * 44100)

    converted = asyncio.run(to_wav_16k_mono(source.getvalue(), "audio/wav"))

    with wave.open(io.BytesIO(converted)) as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1


def test_converting_empty_audio_raises_provider_error():
    with pytest.raises(ProviderError):
        asyncio.run(to_wav_16k_mono(b"", "audio/webm"))