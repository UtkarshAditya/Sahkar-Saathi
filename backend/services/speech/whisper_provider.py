"""Whisper speech-to-text provider (role C). Plain Python, no Django imports.

Implements SpeechProvider from services/types.py using faster-whisper:

    pip install faster-whisper

Settings (environment variables):
    WHISPER_MODEL         default "small"  (use "base" for quick development)
    WHISPER_DEVICE        default "cpu"
    WHISPER_COMPUTE_TYPE  default "int8"   (small and fast on CPU)

Try it on a real recording, from the backend/ folder:
    python -m services.speech.whisper_provider path/to/recording.m4a hi
"""

import asyncio
import io
import logging
import math
import os
import threading

from ..types import ProviderError, ServiceNotReady, Transcript

logger = logging.getLogger(__name__)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# Per-language model overrides if needed
LANGUAGE_MODEL_OVERRIDES = {
    # "ta": "small",
}

# Optional domain vocabulary hint (switched off by default or minimal)
DEFAULT_VOCABULARY_HINT = "PMFBY, Krishi Rakshak, PACS, Kharif, Rabi, grievance, crop insurance."

# Languages we pass to Whisper as a hint. Anything else is auto-detected.
HINT_LANGUAGES = {"en", "hi", "ta", "mr", "te", "kn", "bn", "gu", "pa", "ml", "ur"}

_models = {}
_lock = threading.Lock()


def _get_model(language: str | None = None):
    """Load the model once per size/language, on first use, so the server starts fast."""
    global _models
    model_size = LANGUAGE_MODEL_OVERRIDES.get(language, MODEL_SIZE)
    with _lock:
        if model_size not in _models:
            from faster_whisper import WhisperModel  # imported lazily on purpose

            logger.info("Loading Whisper model %s (%s, %s)", model_size, DEVICE, COMPUTE_TYPE)
            _models[model_size] = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE)
        return _models[model_size]


def _transcribe_sync(
    audio: bytes, language: str | None, initial_prompt: str | None
) -> tuple[str, str, float]:
    """Blocking work. Always run through asyncio.to_thread, never directly in a handler."""
    model = _get_model(language)

    segments, info = model.transcribe(
        io.BytesIO(audio),
        language=language,
        initial_prompt=initial_prompt,
        beam_size=5,
        vad_filter=True,
    )
    parts: list[str] = []
    logprobs: list[float] = []
    for seg in segments:  # decoding actually happens while iterating
        parts.append(seg.text.strip())
        logprobs.append(seg.avg_logprob)
    text = " ".join(p for p in parts if p).strip()

    confidence = math.exp(sum(logprobs) / len(logprobs)) if logprobs else 0.0
    return text, info.language, max(0.0, min(1.0, confidence))


class WhisperSpeechProvider:
    """SpeechProvider with real speech-to-text and robust fallback handling."""

    def __init__(self, synthesizer=None) -> None:
        self.synthesizer = synthesizer

    def warm_up(self, language: str = "en") -> None:
        """Warm up the model to prevent first-request latency."""
        try:
            _get_model(language)
            logger.info("Whisper model warmed up successfully for language: %s", language)
        except Exception as exc:
            logger.warning("Model warm-up failed: %s", exc)

    async def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language_hint: str | None,
        use_vocabulary_hint: bool = False,
    ) -> Transcript:
        if not audio:
            raise ProviderError("No audio received.")

        language = language_hint if language_hint in HINT_LANGUAGES else None
        initial_prompt = DEFAULT_VOCABULARY_HINT if use_vocabulary_hint else None

        logger.info("Transcribing %d bytes (%s), hint=%s", len(audio), content_type, language)

        try:
            # First attempt: direct decoding with faster-whisper
            text, detected, confidence = await asyncio.to_thread(
                _transcribe_sync, audio, language, initial_prompt
            )
        except Exception as direct_exc:
            logger.warning(
                "Direct audio decoding failed (%s). Retrying via ffmpeg fallback...", direct_exc
            )
            try:
                # Fallback attempt: convert via ffmpeg to 16kHz
                # mono WAV locally to avoid circular import
                from .audio import to_wav_16k_mono

                wav_audio = await to_wav_16k_mono(audio, content_type)
                text, detected, confidence = await asyncio.to_thread(
                    _transcribe_sync, wav_audio, language, initial_prompt
                )
            except Exception as exc:
                raise ProviderError(f"Whisper transcription failed after fallback: {exc}") from exc

        return Transcript(text=text, language=detected, confidence=confidence)

    async def synthesize(self, text: str, *, language: str) -> bytes:
        if self.synthesizer is None:
            raise ServiceNotReady("Text to speech is not plugged in yet.")
        return await self.synthesizer.synthesize(text, language=language)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    async def _main(audio: bytes, hint: str | None) -> None:
        provider = WhisperSpeechProvider()
        provider.warm_up(hint or "en")
        result = await provider.transcribe(
            audio, content_type="audio/unknown", language_hint=hint, use_vocabulary_hint=True
        )
        print(f"language={result.language}  confidence={result.confidence:.2f}")
        print(result.text)

    if len(sys.argv) < 2:
        sys.exit("Usage: python -m services.speech.whisper_provider <audio file> [language code]")
    recording = Path(sys.argv[1]).read_bytes()
    asyncio.run(_main(recording, sys.argv[2] if len(sys.argv) > 2 else None))
