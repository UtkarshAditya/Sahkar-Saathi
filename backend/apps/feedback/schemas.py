from typing import Literal

from ninja import Field, Schema
from pydantic import field_validator, model_validator


class FeedbackIn(Schema):
    message_id: str | None = Field(
        None, max_length=64, description="The answer being rated; null for general feedback."
    )
    rating: Literal["up", "down"] | None = None
    reason: str | None = Field(None, max_length=100, description="e.g. 'Wrong state'.")
    comment: str = Field("", max_length=1000)

    @field_validator("reason", "comment")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def check_content(self) -> "FeedbackIn":
        if self.rating and not self.message_id:
            raise ValueError("A rating needs the message_id of the answer it rates.")
        if not self.rating and not self.comment:
            raise ValueError("Send a rating or a comment.")
        return self


class FeedbackOut(Schema):
    id: int
    ok: bool = True
