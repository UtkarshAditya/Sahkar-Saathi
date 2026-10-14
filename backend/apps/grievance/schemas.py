from ninja import Field, Schema
from pydantic import field_validator

from apps.chat.schemas import validate_language

MIN_DESCRIPTION = 20
MAX_DESCRIPTION = 2000


class GrievanceIn(Schema):
    description: str = Field(..., description="The problem in the member's own words.")
    state: str | None = Field(None, max_length=8, description="State code such as TN.")
    language: str = Field("en", description="Short ISO code: en, hi or the regional language.")
    category_hint: str | None = Field(
        None, max_length=40, description="A category id the user picked; null to detect."
    )

    @field_validator("description")
    @classmethod
    def check_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < MIN_DESCRIPTION:
            raise ValueError(
                f"Please describe the problem in at least {MIN_DESCRIPTION} characters."
            )
        if len(value) > MAX_DESCRIPTION:
            raise ValueError(f"Keep the description under {MAX_DESCRIPTION} characters.")
        return value

    @field_validator("language")
    @classmethod
    def check_language(cls, value: str) -> str:
        return validate_language(value)

    @field_validator("state")
    @classmethod
    def clean_state(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value else None


class GrievanceCategoryOut(Schema):
    id: str
    label: str
    description: str


class GrievanceGuideOut(Schema):
    category: GrievanceCategoryOut
    forum: str
    forum_note: str
    steps: list[str]
    documents_needed: list[str]
    draft_text: str = Field(..., description="Editable draft with [placeholders]. Never filed.")
    is_demo: bool
