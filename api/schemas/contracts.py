from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

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
    content_type: Literal["turn", "slide", "section"]
    company_id: int
    company_name: str
    quarter: str | None
    event_date: date | None
    document_type: str
    speaker_name: str | None = None
    speaker_role: str | None = None
    snippet: str
    score: float
    document_id: int


class SearchResponse(BaseModel):
    total: int
    page: int
    results: list[SearchResult]
    took_ms: int


class QARequest(BaseModel):
    question: str = Field(min_length=1)
    company_ids: list[int] | None = None
    quarter_from: str | None = None
    quarter_to: str | None = None
    session_id: str | None = None


class CompanyOut(BaseModel):
    id: int
    scrip_code: str
    name: str
    sector: str | None = None


class FinancialOut(BaseModel):
    id: int
    company_id: int
    period: str
    period_type: str
    period_end_date: date | None
    revenue: Decimal | None
    ebitda: Decimal | None
    ebitda_margin: Decimal | None
    pat: Decimal | None
    eps_basic: Decimal | None
    restated: bool
    quality_flags: list[str] | None


class ManagementChangeOut(BaseModel):
    id: int
    company_id: int
    company_name: str
    filing_date: date
    effective_date: date | None
    change_type: str
    person_name: str
    role: str
    role_category: str
    reason: str | None
    din: str | None
    raw_text: str
    extraction_confidence: float | None


class PaginatedManagementChanges(BaseModel):
    total: int
    page: int
    results: list[ManagementChangeOut]


class HealthResponse(BaseModel):
    status: str
    db: str
    es: str
    timestamp: datetime
    details: dict[str, Any] = {}
