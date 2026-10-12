"""Thin speech endpoints: upload checks and response shaping only.

Audio conversion (to 16 kHz mono WAV with ffmpeg) and Bhashini/Whisper calls live in
member C's SpeechProvider, never here.
"""

import logging
import time

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpResponse
from ninja import File, Form, Router, UploadedFile

from apps.chat.schemas import validate_language
from config.errors import ApiError, ErrorOut
from config.services import get_speech_provider

from .schemas import SynthesizeIn, TranscriptOut

logger = logging.getLogger("sahkar.api.speech")

router = Router()


def _base_content_type(value: str | None) -> str:
    # Browsers send e.g. "audio/webm;codecs=opus".
    return (value or "").split(";", 1)[0].strip().strip("\"'").lower()


@router.post(
    "/transcribe",
    response={
        200: TranscriptOut,
        400: ErrorOut,
        413: ErrorOut,
        415: ErrorOut,
        422: ErrorOut,
        502: ErrorOut,
        503: ErrorOut,
    },
    summary="Speech to text",
)
async def transcribe(
    request,
    audio: UploadedFile = File(
        ..., description="Recorded question, e.g. audio/webm from MediaRecorder."
    ),
    language_hint: str | None = Form(None, description="en, hi or the regional language."),
):
    """Transcribe a spoken question. The client shows the text for the user to confirm."""
    content_type = _base_content_type(audio.content_type)
    if content_type not in settings.SPEECH_ALLOWED_CONTENT_TYPES:
        raise ApiError(
            415, "unsupported_audio_type", f"Audio type '{content_type}' is not supported."
        )
    if audio.size is not None and audio.size > settings.SPEECH_MAX_UPLOAD_BYTES:
        limit_mb = settings.SPEECH_MAX_UPLOAD_BYTES / (1024 * 1024)
        raise ApiError(413, "audio_too_large", f"Recording is larger than {limit_mb:g} MB.")
    if not audio.size:
        raise ApiError(400, "empty_audio", "The recording is empty.")

    hint = None
    if language_hint:
        try:
            hint = validate_language(language_hint)
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc

    data = await sync_to_async(audio.read)()
    started = time.perf_counter()
    transcript = await get_speech_provider().transcribe(
        data, content_type=content_type, language_hint=hint
    )
    logger.info(
        "speech.transcribe bytes=%d type=%s language=%s latency_ms=%d",
        len(data),
        content_type,
        transcript.language,
        (time.perf_counter() - started) * 1000,
    )
    return TranscriptOut(
        text=transcript.text,
        language=transcript.language,
        confidence=transcript.confidence,
        is_demo=transcript.is_demo,
    )


@router.post(
    "/synthesize",
    response={422: ErrorOut, 502: ErrorOut, 503: ErrorOut},
    summary="Text to speech",
    openapi_extra={
        "responses": {
            200: {
                "description": "16 kHz mono WAV audio of the text.",
                "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
            }
        }
    },
)
async def synthesize(request, payload: SynthesizeIn):
    """Read an answer aloud. Returns WAV audio for the Listen button."""
    started = time.perf_counter()
    audio = await get_speech_provider().synthesize(payload.text, language=payload.language)
    logger.info(
        "speech.synthesize chars=%d language=%s bytes=%d latency_ms=%d",
        len(payload.text),
        payload.language,
        len(audio),
        (time.perf_counter() - started) * 1000,
    )
    response = HttpResponse(audio, content_type="audio/wav")
    response["Cache-Control"] = "no-store"
    return response
