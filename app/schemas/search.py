from datetime import date

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2)
    companies: list[int] | None = None
    quarter_from: str | None = None
    quarter_to: str | None = None
    document_types: list[str] | None = None
    speaker_roles: list[str] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    id: int
    content_type: str
    company_id: int
    company_name: str
    quarter: str | None
    event_date: date | None
    document_type: str
    speaker_name: str | None
    speaker_role: str | None
    snippet: str
    score: float
    document_id: int


class SearchResponse(BaseModel):
    total: int
    page: int
    results: list[SearchResult]
    took_ms: int
