"""Lesson content. These models validate data/lessons*.yaml AND are the API response."""

from typing import Literal

from ninja import Field, Schema
from pydantic import model_validator


class LessonSectionOut(Schema):
    heading: str
    body: str


class LessonOut(Schema):
    slug: str
    title: str
    summary: str
    reading_minutes: int = Field(..., ge=1, le=30)
    icon: Literal["loan", "card", "savings", "fraud"]
    sections: list[LessonSectionOut] = Field(..., min_length=1)
    key_points: list[str]


class QuizQuestionOut(Schema):
    id: str
    question: str
    options: list[str] = Field(..., min_length=2)
    correct_index: int = Field(..., ge=0)
    explanation: str

    @model_validator(mode="after")
    def index_in_range(self) -> "QuizQuestionOut":
        if self.correct_index >= len(self.options):
            raise ValueError(f"Quiz question '{self.id}' has correct_index out of range.")
        return self


class LessonsOut(Schema):
    language: str = Field(..., description="Language of the content actually returned.")
    lessons: list[LessonOut]
    quiz: list[QuizQuestionOut]
