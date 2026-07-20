from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    error: str
    code: str


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scrip_code: str
    name: str
    sector: str | None = None


class CompanyDetail(CompanySummary):
    isin: str | None = None
    sub_sector: str | None = None
    bse_id: str | None = None
    active: bool
    coverage: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    bse_filing_id: str | None
    event_date: date
    event_type: str
    quarter: str | None
    fy_year: int | None
    filing_url: str | None


class FinancialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    document_id: int | None
    period: str
    period_type: str
    period_end_date: date | None
    revenue: Decimal | None
    ebitda: Decimal | None
    ebitda_margin: Decimal | None
    da: Decimal | None
    ebit: Decimal | None
    finance_costs: Decimal | None
    pbt: Decimal | None
    tax: Decimal | None
    pat: Decimal | None
    eps_basic: Decimal | None
    eps_diluted: Decimal | None
    shares_cr: Decimal | None
    currency: str
    unit: str
    restated: bool
    restatement_note: str | None
    extraction_method: str | None
    quality_flags: list[str] | None


class ManagementChangeOut(BaseModel):
    id: int
    company_id: int
    company_name: str
    document_id: int | None
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


class HealthResponse(BaseModel):
    status: str
    db: str
    storage: str
    timestamp: datetime
