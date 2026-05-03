from elasticsearch import Elasticsearch
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company
from app.models.document import Document
from app.models.event import Event
from app.models.press_release import PressReleaseSection
from app.models.slide import Slide
from app.models.turn import Turn
from app.services.search_service import ensure_index, get_es_client


def _base_metadata(document: Document, event: Event, company: Company) -> dict:
    return {
        "company_id": company.id,
        "company_name": company.name,
        "quarter": event.quarter,
        "fy_year": event.fy_year,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "document_type": document.document_type,
        "document_id": document.id,
    }


def index_document_content(db: Session, document_id: int, client: Elasticsearch | None = None) -> int:
    es = client or get_es_client()
    ensure_index(es)
    document, event, company = db.execute(
        select(Document, Event, Company).join(Event, Event.id == Document.event_id).join(Company, Company.id == Event.company_id).where(Document.id == document_id)
    ).one()
    base = _base_metadata(document, event, company)
    count = 0
    for turn in db.scalars(select(Turn).where(Turn.document_id == document_id, Turn.speaker_role != "moderator")):
        es.index(index=settings.es_index_name, id=f"turn-{turn.id}", document={**base, "text": turn.text, "speaker_role": turn.speaker_role, "speaker_name": turn.speaker_name, "turn_id": turn.id})
        count += 1
    for slide in db.scalars(select(Slide).where(Slide.document_id == document_id)):
        text = f"{slide.title or ''}\n{slide.body_text or ''}".strip()
        es.index(index=settings.es_index_name, id=f"slide-{slide.id}", document={**base, "text": text, "speaker_role": "n_a", "speaker_name": None, "slide_id": slide.id})
        count += 1
    for section in db.scalars(select(PressReleaseSection).where(PressReleaseSection.document_id == document_id)):
        es.index(index=settings.es_index_name, id=f"section-{section.id}", document={**base, "text": section.text, "speaker_role": "press_release", "speaker_name": None, "section_type": section.section_type, "section_id": section.id})
        count += 1
    return count
