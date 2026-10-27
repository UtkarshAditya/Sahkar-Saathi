"""Whisper speech-to-text provider (role C). Plain Python, no Django imports.

Implements SpeechProvider from services/types.py using faster-whisper:

    pip install faster-whisper "av>=11,<19"

Settings (environment variables, all optional):
    WHISPER_MODEL         default "small" (use "base" for quick development)
    WHISPER_MODEL_<LANG>  model for one language, e.g. WHISPER_MODEL_HI=medium
    WHISPER_DEVICE        default "cpu"
    WHISPER_COMPUTE_TYPE  default "int8" (small and fast on CPU)
    WHISPER_BEAM_SIZE     default 5
    WHISPER_USE_PROMPT    default 0. Set to 1 to give Whisper a short list of domain words
                          for the language. Measure with eval_stt before switching it on.

Try it on a real recording, from the backend/ folder:
    python -m services.speech.whisper_provider path/to/recording.m4a hi

Download and load the models once, ahead of the demo:
    python -m services.speech.whisper_provider --warmup
"""

import asyncio
import io
import logging
import math
import os
import threading
import time

from ..types import ProviderError, ServiceNotReady, Transcript
from .audio import to_wav_16k_mono

logger = logging.getLogger(__name__)

# Languages we pass to Whisper as a hint. Anything else is auto-detected.
HINT_LANGUAGES = {"en", "hi", "ta", "mr", "te", "kn", "bn", "gu", "pa", "ml", "ur"}

# Short domain-word hints, written in each language so they do not pull the
# output towards English. Only used when WHISPER_USE_PROMPT=1.
# Ask a native speaker to check the Hindi and Tamil wording.
DOMAIN_PROMPTS = {
    "en": "Crop insurance, PMFBY, cooperative society, PACS, grievance.",
    "hi": "फसल बीमा, प्रधानमंत्री फसल बीमा योजना, सहकारी समिति, पैक्स, शिकायत।",
    "ta": "பயிர் காப்பீடு, பிரதம மந்திரி பயிர் காப்பீட்டுத் திட்டம், கூட்டுறவு சங்கம், புகார்.",
}

_models: dict[str, object] = {}
_lock = threading.Lock()


def _model_name_for(language: str | None) -> str:
    if language:
        override = os.getenv(f"WHISPER_MODEL_{language.upper()}")
        if override:
            return override
    return os.getenv("WHISPER_MODEL", "small")


def _get_model(name: str):
    """Load each model size once, on first use, so the server starts fast."""
    with _lock:
        if name not in _models:
            from faster_whisper import WhisperModel  # imported lazily on purpose

            device = os.getenv("WHISPER_DEVICE", "cpu")
            compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
            logger.info("Loading Whisper model %s (%s, %s)", name, device, compute_type)
            _models[name] = WhisperModel(name, device=device, compute_type=compute_type)
        return _models[name]


def _is_decode_error(exc: Exception) -> bool:
    """PyAV, the audio decoder inside faster-whisper, raises errors from the 'av' package."""
    return type(exc).__module__.split(".")[0] == "av"


def _transcribe_sync(audio: bytes, language: str | None) -> tuple[str, str, float]:
    """Blocking work. Always run through asyncio.to_thread, never directly in a handler."""
    model = _get_model(_model_name_for(language))
    options = {
        "language": language,
        "beam_size": int(os.getenv("WHISPER_BEAM_SIZE", "5")),
        "vad_filter": True,
        # Stops one bad guess from being repeated through the rest of the clip.
        "condition_on_previous_text": False,
    }
    if os.getenv("WHISPER_USE_PROMPT", "0") == "1" and language in DOMAIN_PROMPTS:
        options["initial_prompt"] = DOMAIN_PROMPTS[language]

    # faster-whisper decodes WebM/MP4 itself, so no ffmpeg step is needed here.
    segments, info = model.transcribe(io.BytesIO(audio), **options)
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


async def warm_up(languages=("en", "hi", "ta")) -> None:
    """Load the models the given languages need, so the first real request is fast."""
    for name in sorted({_model_name_for(lang) for lang in languages}):
        await asyncio.to_thread(_get_model, name)


class WhisperSpeechProvider:
    """SpeechProvider with real speech-to-text.

    Whisper does not do text-to-speech. Pass a `synthesizer` (any object with an
    async synthesize(text, *, language) -> bytes), for example the stub provider
    for now. Without one, synthesize raises ServiceNotReady.
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
        started = time.perf_counter()
        try:
            try:
                text, detected, confidence = await asyncio.to_thread(
                    _transcribe_sync, audio, language
                )
            except Exception as exc:
                if not _is_decode_error(exc):
                    raise
                # Some browser recordings cannot be decoded directly. Convert to
                # 16 kHz mono WAV with ffmpeg and try once more.
                logger.info("Could not decode %s directly (%s); using ffmpeg", content_type, exc)
                wav = await to_wav_16k_mono(audio, content_type)
                text, detected, confidence = await asyncio.to_thread(
                    _transcribe_sync, wav, language
                )
        except ProviderError:
            raise
        except Exception as exc:  # missing package, model error, undecodable audio
            raise ProviderError(f"Whisper transcription failed: {exc}") from exc
        logger.info("Transcribed in %.1fs (language=%s)", time.perf_counter() - started, detected)
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
        sys.exit(
            "Usage: python -m services.speech.whisper_provider <audio file> [language code]\n"
            "       python -m services.speech.whisper_provider --warmup"
        )
    if sys.argv[1] == "--warmup":
        asyncio.run(warm_up())
        print("Models loaded.")
        sys.exit(0)
    # Read the file here, in normal (non-async) code, then hand the bytes to the async function.
    recording = Path(sys.argv[1]).read_bytes()
    asyncio.run(_main(recording, sys.argv[2] if len(sys.argv) > 2 else None))