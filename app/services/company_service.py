from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.document import Document
from app.models.event import Event
from app.models.financial import Financial
from app.schemas.common import CompanyDetail


def list_companies(db: Session) -> list[Company]:
    return list(db.scalars(select(Company).where(Company.active.is_(True)).order_by(Company.name)))


def get_company_detail(db: Session, company_id: int) -> CompanyDetail | None:
    company = db.get(Company, company_id)
    if not company:
        return None
    coverage_rows = db.execute(
        select(Document.document_type, Document.extraction_status, func.count(Document.id))
        .join(Event, Event.id == Document.event_id)
        .where(Event.company_id == company_id)
        .group_by(Document.document_type, Document.extraction_status)
    ).all()
    coverage = {}
    for document_type, status, count in coverage_rows:
        coverage.setdefault(document_type, {})[status] = count
    return CompanyDetail.model_validate(company).model_copy(update={"coverage": coverage})


def list_company_events(db: Session, company_id: int, quarter: str | None = None) -> list[Event]:
    stmt = select(Event).where(Event.company_id == company_id).order_by(Event.event_date.desc())
    if quarter:
        stmt = stmt.where(Event.quarter == quarter)
    return list(db.scalars(stmt))


def list_company_financials(db: Session, company_id: int, from_period: str | None = None, to_period: str | None = None) -> list[Financial]:
    stmt = select(Financial).where(Financial.company_id == company_id).order_by(Financial.period)
    if from_period:
        stmt = stmt.where(Financial.period >= from_period)
    if to_period:
        stmt = stmt.where(Financial.period <= to_period)
    return list(db.scalars(stmt))
