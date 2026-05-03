from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.document import Document
from app.models.event import Event
from app.models.turn import Turn
from app.schemas.documents import CoverageRow


def list_event_documents(db: Session, event_id: int) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.event_id == event_id).order_by(Document.id)))


def list_transcript_turns(db: Session, document_id: int) -> list[Turn]:
    return list(db.scalars(select(Turn).where(Turn.document_id == document_id).order_by(Turn.turn_index)))


def coverage_dashboard(db: Session) -> list[CoverageRow]:
    rows = db.execute(
        select(
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            Document.document_type,
            Document.extraction_status,
            func.count(Document.id).label("documents"),
            func.avg(Document.quality_score).label("avg_quality"),
        )
        .join(Event, Event.company_id == Company.id, isouter=True)
        .join(Document, Document.event_id == Event.id, isouter=True)
        .group_by(Company.id, Company.name, Document.document_type, Document.extraction_status)
        .order_by(Company.name)
    ).all()
    return [
        CoverageRow(
            company_id=row.company_id,
            company_name=row.company_name,
            document_type=row.document_type,
            extraction_status=row.extraction_status,
            documents=row.documents,
            avg_quality=float(row.avg_quality) if row.avg_quality is not None else None,
        )
        for row in rows
    ]
