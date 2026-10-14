"""Scheme content. These models validate data/schemes.yaml AND are the API responses,
so the content file and the contract cannot drift apart."""

from datetime import date
from typing import Literal

from ninja import Field, Schema
from pydantic import model_validator

SchemeCategory = Literal[
    "cooperative-development", "credit", "insurance", "storage-marketing", "digital-services"
]
FactKind = Literal["eligibility", "enrolment", "premium", "loss-reporting", "official-info"]


class SchemeFactOut(Schema):
    id: str
    kind: FactKind
    title: str
    body: str
    source_label: str = Field(..., min_length=1)
    source_url: str | None = Field(..., description="Null until verified.")
    as_of: date | None = Field(..., description="Null until verified.")
    is_placeholder: bool
    season: Literal["kharif", "rabi", "commercial"] | None = Field(
        None, description="Applies to one season only; null means all seasons."
    )
    crop_type: Literal["food", "oilseed", "horticulture"] | None = Field(
        None, description="Applies to one crop type only; null means all."
    )

    @model_validator(mode="after")
    def verified_needs_source(self) -> "SchemeFactOut":
        if not self.is_placeholder and not (self.source_url and self.as_of):
            raise ValueError(
                f"Fact '{self.id}' is not a placeholder, so it needs source_url and as_of."
            )
        return self


class SchemeOut(Schema):
    slug: str
    title: str
    category: SchemeCategory
    summary: str
    eligibility: str
    how_to_access: str
    source_label: str = Field(..., min_length=1)
    source_url: str | None = Field(..., description="Null until a verified link is recorded.")
    as_of: date
    is_sample: bool

    @model_validator(mode="after")
    def verified_needs_source(self) -> "SchemeOut":
        if not self.is_sample and not self.source_url:
            raise ValueError(f"Scheme '{self.slug}' is not a sample, so it needs a source_url.")
        return self


class SchemeDetailOut(SchemeOut):
    facts: list[SchemeFactOut] = Field(
        default_factory=list, description="Guide facts, e.g. for the PMFBY crop insurance guide."
    )


class SchemesFile(Schema):
    schemes: list[SchemeDetailOut]

    @model_validator(mode="after")
    def unique_slugs(self) -> "SchemesFile":
        slugs = [s.slug for s in self.schemes]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Scheme slugs must be unique.")
        return self
