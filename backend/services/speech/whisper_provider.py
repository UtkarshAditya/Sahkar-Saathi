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

# Languages we pass to Whisper as a hint. Anything else is auto-detected.
HINT_LANGUAGES = {"en", "hi", "ta", "mr", "te", "kn", "bn", "gu", "pa", "ml", "ur"}

_model = None
_lock = threading.Lock()


def _get_model():
    """Load the model once, on first use, so the server starts fast."""
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel  # imported lazily on purpose

            logger.info("Loading Whisper model %s (%s, %s)", MODEL_SIZE, DEVICE, COMPUTE_TYPE)
            _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        return _model


def _transcribe_sync(audio: bytes, language: str | None) -> tuple[str, str, float]:
    """Blocking work. Always run through asyncio.to_thread, never directly in a handler."""
    model = _get_model()
    # faster-whisper decodes WebM/MP4 itself, so no ffmpeg step is needed here.
    segments, info = model.transcribe(
        io.BytesIO(audio), language=language, beam_size=5, vad_filter=True
    )
    parts: list[str] = []
    logprobs: list[float] = []
    for seg in segments:  # decoding actually happens while iterating
        parts.append(seg.text.strip())
        logprobs.append(seg.avg_logprob)
    text = " ".join(p for p in parts if p).strip()
    # Whisper has no true confidence score. exp(mean log-probability) is a common
    # proxy in 0..1. Treat it as a rough signal, not a measured accuracy.
    confidence = math.exp(sum(logprobs) / len(logprobs)) if logprobs else 0.0
    return text, info.language, max(0.0, min(1.0, confidence))


class WhisperSpeechProvider:
    """SpeechProvider with real speech-to-text.

    Whisper does not do text-to-speech. Pass a `synthesizer` (any object with an
    async synthesize(text, *, language) -> bytes), for example the stub provider
    for now and the Bhashini provider later. Without one, synthesize raises
    ServiceNotReady.
    """

    def __init__(self, synthesizer=None) -> None:
        self.synthesizer = synthesizer

    async def transcribe(
        self, audio: bytes, *, content_type: str, language_hint: str | None
    ) -> Transcript:
        if not audio:
            raise ProviderError("No audio received.")
        language = language_hint if language_hint in HINT_LANGUAGES else None
        logger.info("Transcribing %d bytes (%s), hint=%s", len(audio), content_type, language)
        try:
            text, detected, confidence = await asyncio.to_thread(_transcribe_sync, audio, language)
        except Exception as exc:  # missing package, undecodable audio, model error
            raise ProviderError(f"Whisper transcription failed: {exc}") from exc
        return Transcript(text=text, language=detected, confidence=confidence)

    async def synthesize(self, text: str, *, language: str) -> bytes:
        if self.synthesizer is None:
            raise ServiceNotReady("Text to speech is not plugged in yet.")
        return await self.synthesizer.synthesize(text, language=language)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    async def _main(audio: bytes, hint: str | None) -> None:
        result = await WhisperSpeechProvider().transcribe(
            audio, content_type="audio/unknown", language_hint=hint
        )
        print(f"language={result.language}  confidence={result.confidence:.2f}")
        print(result.text)

    if len(sys.argv) < 2:
        sys.exit("Usage: python -m services.speech.whisper_provider <audio file> [language code]")
    # Read the file here, in normal (non-async) code, then hand the bytes to the async function.
    recording = Path(sys.argv[1]).read_bytes()
    asyncio.run(_main(recording, sys.argv[2] if len(sys.argv) > 2 else None))
