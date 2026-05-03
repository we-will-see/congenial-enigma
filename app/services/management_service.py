from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.management_change import ManagementChange
from app.schemas.common import ManagementChangeOut


def list_management_changes(
    db: Session,
    company_id: int | None = None,
    role_category: str | None = None,
    change_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[ManagementChangeOut]]:
    clauses = []
    if company_id:
        clauses.append(ManagementChange.company_id == company_id)
    if role_category:
        clauses.append(ManagementChange.role_category == role_category)
    if change_type:
        clauses.append(ManagementChange.change_type == change_type)
    if from_date:
        clauses.append(ManagementChange.filing_date >= from_date)
    if to_date:
        clauses.append(ManagementChange.filing_date <= to_date)

    base = select(ManagementChange, Company.name.label("company_name")).join(Company, Company.id == ManagementChange.company_id)
    count_stmt = select(func.count(ManagementChange.id))
    if clauses:
        condition = and_(*clauses)
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(base.order_by(ManagementChange.filing_date.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    return total, [
        ManagementChangeOut(
            id=row.ManagementChange.id,
            company_id=row.ManagementChange.company_id,
            company_name=row.company_name,
            document_id=row.ManagementChange.document_id,
            filing_date=row.ManagementChange.filing_date,
            effective_date=row.ManagementChange.effective_date,
            change_type=row.ManagementChange.change_type,
            person_name=row.ManagementChange.person_name,
            role=row.ManagementChange.role,
            role_category=row.ManagementChange.role_category,
            reason=row.ManagementChange.reason,
            din=row.ManagementChange.din,
            raw_text=row.ManagementChange.raw_text,
            extraction_confidence=row.ManagementChange.extraction_confidence,
        )
        for row in rows
    ]
