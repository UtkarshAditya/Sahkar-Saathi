"""Choose the speech provider (role C). Plain Python, no Django imports.

    SPEECH_PROVIDER=stub      canned transcript and silent audio (the default)
    SPEECH_PROVIDER=whisper   real speech to text with Whisper

Whisper does not do text to speech, so with "whisper" the Listen button still gets the
stub's silent audio until a real voice is added. Call build_speech_provider() where the
speech provider is created, in place of StubSpeechProvider().
"""

import os

from ..stubs import StubSpeechProvider
from .whisper_provider import WhisperSpeechProvider


def build_speech_provider(name: str | None = None):
    chosen = (name or os.getenv("SPEECH_PROVIDER", "stub")).strip().lower()
    if chosen == "whisper":
        return WhisperSpeechProvider(synthesizer=StubSpeechProvider())
    if chosen == "stub":
        return StubSpeechProvider()
    raise ValueError(f"Unknown SPEECH_PROVIDER {chosen!r}. Use 'stub' or 'whisper'.")
