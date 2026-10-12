"""Request and response schemas for /chat. These are the contract the React app builds on."""

from typing import Literal

from django.conf import settings
from ninja import Field, Schema
from pydantic import field_validator


def validate_language(value: str) -> str:
    value = value.strip().lower()
    if value not in settings.SUPPORTED_LANGUAGES:
        allowed = ", ".join(settings.SUPPORTED_LANGUAGES)
        raise ValueError(f"Unsupported language '{value}'. Use one of: {allowed}.")
    return value


class AskIn(Schema):
    conversation_id: str | None = Field(
        None, max_length=64, description="Omit on the first question; reuse the returned id."
    )
    text: str = Field(..., min_length=1, description="The question, typed or confirmed transcript.")
    language: str = Field("en", description="Short ISO code: en, hi or the regional language.")
    state: str | None = Field(
        None, max_length=8, description="State code such as MH, or null if not chosen."
    )
    document_id: str | None = Field(
        None, max_length=64, description="Limit retrieval to one library document."
    )

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be empty.")
        if len(value) > settings.CHAT_MAX_QUESTION_CHARS:
            raise ValueError(
                f"Keep the question under {settings.CHAT_MAX_QUESTION_CHARS} characters."
            )
        return value

    @field_validator("language")
    @classmethod
    def check_language(cls, value: str) -> str:
        return validate_language(value)

    @field_validator("state")
    @classmethod
    def clean_state(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value else None


class CitationOut(Schema):
    id: str
    document_id: str
    title: str
    publisher: str
    published_date: str = Field(..., description="ISO date.")
    page: int | None
    section: str | None = None
    url: str | None = Field(None, description="Null until a verified source URL is recorded.")
    excerpt: str | None = None


class ContactOut(Schema):
    label: str
    detail: str


class AskOut(Schema):
    conversation_id: str
    message_id: str
    answer_text: str
    status: Literal["answered", "partial", "declined"]
    needs_state: bool = Field(..., description="True when the user must choose a state first.")
    citations: list[CitationOut] = Field(..., description="Always empty for a declined answer.")
    followups: list[str]
    contact: ContactOut | None = Field(None, description="Always set for a declined answer.")
    is_demo: bool = Field(..., description="True for stub or cached answers.")
