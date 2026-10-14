from datetime import date
from typing import Literal

from ninja import Field, Schema

DocType = Literal["act", "rules", "model-bylaws", "circular", "scheme-guideline"]


class DocumentOut(Schema):
    id: str
    title: str
    publisher: str
    doc_type: DocType
    state: str = Field(..., description='A state code, or "central".')
    language: str
    published_date: date
    version: str
    status: Literal["active", "retired"]
    source_url: str | None = Field(..., description="Null until a verified link is recorded.")
    is_sample: bool

    @staticmethod
    def resolve_source_url(obj) -> str | None:
        return obj.source_url or None
