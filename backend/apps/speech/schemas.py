from django.conf import settings
from ninja import Field, Schema
from pydantic import field_validator

from apps.chat.schemas import validate_language


class TranscriptOut(Schema):
    text: str = Field(..., description="Show this as an editable transcript before sending.")
    language: str
    confidence: float = Field(..., ge=0, le=1)
    is_demo: bool


class SynthesizeIn(Schema):
    text: str = Field(..., min_length=1)
    language: str = Field("en", description="Short ISO code: en, hi or the regional language.")

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be empty.")
        if len(value) > settings.SPEECH_MAX_SYNTH_CHARS:
            raise ValueError(f"Keep the text under {settings.SPEECH_MAX_SYNTH_CHARS} characters.")
        return value

    @field_validator("language")
    @classmethod
    def check_language(cls, value: str) -> str:
        return validate_language(value)
