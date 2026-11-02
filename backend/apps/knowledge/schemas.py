from datetime import date, datetime
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
    published_date: date | None = Field(..., description="Null when the source states no date.")
    version: str
    status: Literal["active", "retired"]
    source_url: str | None = Field(..., description="Null until a verified link is recorded.")
    is_sample: bool
    source_kind: Literal["pdf", "web"] = Field("pdf", description="Where the text came from.")
    fetched_at: datetime | None = Field(
        None, description="When a web page was last fetched; null for PDFs."
    )

    @staticmethod
    def resolve_source_url(obj) -> str | None:
        return obj.source_url or None
