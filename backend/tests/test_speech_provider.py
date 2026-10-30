"""Tests for the Whisper speech provider, the audio helper and the error-rate maths (role C).

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
from services.speech.eval_stt import error_rate, normalize
from services.speech.whisper_provider import WhisperSpeechProvider, warm_up
from services.types import ProviderError, ServiceNotReady

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def _wav_bytes(rate=44100, channels=2):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x01" * rate)
    return buffer.getvalue()


@pytest.fixture
def fake_whisper(monkeypatch):
    """Replace faster-whisper with a fake model. Returns what the fake saw."""
    for name in ("WHISPER_MODEL", "WHISPER_MODEL_HI", "WHISPER_MODEL_TA", "WHISPER_USE_PROMPT"):
        monkeypatch.delenv(name, raising=False)
    calls, loaded = [], []

    class FakeModel:
        def __init__(self, name, **kwargs):
            loaded.append(name)

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
    monkeypatch.setattr(whisper_provider, "_models", {})  # force fresh "loads"
    return types.SimpleNamespace(calls=calls, loaded=loaded)


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
    assert fake_whisper.calls[-1]["language"] == "ta"


def test_unsupported_language_hint_falls_back_to_auto_detect(fake_whisper):
    _transcribe(hint="xx")
    assert fake_whisper.calls[-1]["language"] is None


def test_empty_audio_raises_provider_error(fake_whisper):
    with pytest.raises(ProviderError):
        _transcribe(audio=b"")


def test_model_failure_becomes_provider_error_without_ffmpeg_retry(fake_whisper, monkeypatch):
    attempts = []

    def boom(audio, language):
        attempts.append(audio)
        raise RuntimeError("model exploded")

    monkeypatch.setattr(whisper_provider, "_transcribe_sync", boom)
    with pytest.raises(ProviderError):
        _transcribe()
    assert len(attempts) == 1  # not a decode error, so no second try


@needs_ffmpeg
def test_decode_failure_is_retried_with_converted_wav(monkeypatch):
    decode_error = type("InvalidDataError", (Exception,), {"__module__": "av.error"})
    seen = []

    def fake_sync(audio, language):
        seen.append(audio)
        if len(seen) == 1:
            raise decode_error("cannot decode")
        return "ok", "hi", 0.9

    monkeypatch.setattr(whisper_provider, "_transcribe_sync", fake_sync)
    provider = WhisperSpeechProvider()
    original = _wav_bytes(rate=44100, channels=2)
    result = asyncio.run(
        provider.transcribe(original, content_type="audio/wav", language_hint="hi")
    )
    assert result.text == "ok"
    assert len(seen) == 2
    with wave.open(io.BytesIO(seen[1])) as wav:  # the retry got 16 kHz mono audio
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1


def test_default_model_is_small_and_is_loaded_once(fake_whisper):
    _transcribe(hint="hi")
    _transcribe(hint="hi")
    assert fake_whisper.loaded == ["small"]


def test_language_can_use_its_own_model(fake_whisper, monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL_HI", "medium")
    _transcribe(hint="hi")
    _transcribe(hint="en")
    assert fake_whisper.loaded == ["medium", "small"]


def test_warm_up_loads_each_distinct_model_once(fake_whisper, monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL_HI", "medium")
    asyncio.run(warm_up(("en", "hi", "ta")))
    assert sorted(fake_whisper.loaded) == ["medium", "small"]


def test_domain_prompt_is_off_by_default(fake_whisper):
    _transcribe(hint="hi")
    assert "initial_prompt" not in fake_whisper.calls[-1]


def test_domain_prompt_can_be_switched_on(fake_whisper, monkeypatch):
    monkeypatch.setenv("WHISPER_USE_PROMPT", "1")
    _transcribe(hint="hi")
    assert fake_whisper.calls[-1]["initial_prompt"]
    _transcribe(hint="xx")  # language unknown, so no prompt
    assert "initial_prompt" not in fake_whisper.calls[-1]


def test_synthesize_without_a_synthesizer_is_not_ready():
    with pytest.raises(ServiceNotReady):
        asyncio.run(WhisperSpeechProvider().synthesize("hello", language="en"))


def test_synthesize_delegates_to_the_given_synthesizer():
    class FakeSynth:
        async def synthesize(self, text, *, language):
            return b"WAV-BYTES"

    provider = WhisperSpeechProvider(synthesizer=FakeSynth())
    assert asyncio.run(provider.synthesize("hello", language="en")) == b"WAV-BYTES"


@needs_ffmpeg
def test_audio_is_converted_to_16khz_mono_wav():
    converted = asyncio.run(to_wav_16k_mono(_wav_bytes(), "audio/wav"))
    with wave.open(io.BytesIO(converted)) as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1


def test_converting_empty_audio_raises_provider_error():
    with pytest.raises(ProviderError):
        asyncio.run(to_wav_16k_mono(b"", "audio/webm"))


def test_word_error_rate():
    assert error_rate("a b c", "a x c", "word") == pytest.approx(1 / 3)
    assert error_rate("a b c", "a b c", "word") == 0.0


def test_character_error_rate_ignores_spaces():
    assert error_rate("ab cd", "abcd", "char") == 0.0


def test_error_rate_with_empty_reference():
    assert error_rate("", "", "word") == 0.0
    assert error_rate("", "something", "word") == 1.0


def test_normalize_drops_punctuation_but_keeps_hindi_vowel_signs():
    assert normalize("फसल बीमा कब? ।") == "फसल बीमा कब"
    assert normalize("When should it be reported?") == "when should it be reported"
