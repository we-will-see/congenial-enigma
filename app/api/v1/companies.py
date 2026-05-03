from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import CompanyDetail, CompanySummary, EventOut, FinancialOut
from app.services.company_service import get_company_detail, list_companies, list_company_events, list_company_financials

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanySummary])
def companies(db: Session = Depends(get_db)) -> list[CompanySummary]:
    return [CompanySummary.model_validate(company) for company in list_companies(db)]


@router.get("/{company_id}", response_model=CompanyDetail)
def company_detail(company_id: int, db: Session = Depends(get_db)) -> CompanyDetail:
    company = get_company_detail(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"error": "Company not found", "code": "COMPANY_NOT_FOUND"})
    return company


@router.get("/{company_id}/events", response_model=list[EventOut])
def company_events(company_id: int, quarter: str | None = None, db: Session = Depends(get_db)) -> list[EventOut]:
    return [EventOut.model_validate(event) for event in list_company_events(db, company_id, quarter)]


@router.get("/{company_id}/financials", response_model=list[FinancialOut])
def company_financials(
    company_id: int,
    from_period: str | None = Query(default=None, alias="from"),
    to_period: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> list[FinancialOut]:
    return [FinancialOut.model_validate(row) for row in list_company_financials(db, company_id, from_period, to_period)]
