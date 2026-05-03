from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ManagementChangeOut
from app.services.management_service import list_management_changes

router = APIRouter(prefix="/management-changes", tags=["management-changes"])


class ManagementChangePage(BaseModel):
    total: int
    page: int
    results: list[ManagementChangeOut]


@router.get("", response_model=ManagementChangePage)
def management_changes(
    company_id: int | None = None,
    role_category: str | None = None,
    change_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ManagementChangePage:
    total, rows = list_management_changes(db, company_id, role_category, change_type, from_date, to_date, page, page_size)
    return ManagementChangePage(total=total, page=page, results=rows)
