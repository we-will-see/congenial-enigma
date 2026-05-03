from __future__ import annotations

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.db.models import Document, Event, PressReleaseSection, Slide, Turn

ES_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text", "analyzer": "english", "fields": {"keyword": {"type": "keyword"}}},
            "company_id": {"type": "integer"},
            "company_name": {"type": "keyword"},
            "quarter": {"type": "keyword"},
            "fy_year": {"type": "integer"},
            "event_date": {"type": "date"},
            "document_type": {"type": "keyword"},
            "speaker_role": {"type": "keyword"},
            "speaker_name": {"type": "keyword"},
            "section_type": {"type": "keyword"},
            "turn_id": {"type": "long"},
            "slide_id": {"type": "long"},
            "section_id": {"type": "long"},
            "document_id": {"type": "integer"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {"analyzer": {"english": {"tokenizer": "standard", "filter": ["lowercase", "english_stop", "english_stemmer"]}}},
    },
}


class ESIndexer:
    def __init__(self) -> None:
        settings = get_settings()
        self.index = settings.es_index_name
        self.client = Elasticsearch(settings.es_host, request_timeout=5)

    def ensure_index(self) -> None:
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(index=self.index, **ES_MAPPING)

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except ElasticsearchException:
            return False

    def index_document_content(self, db: Session, document: Document) -> int:
        self.ensure_index()
        count = 0
        event = db.scalar(select(Event).where(Event.id == document.event_id))
        company = event.company if event else None
        for turn in db.scalars(select(Turn).where(Turn.document_id == document.id)).all():
            self.client.index(index=self.index, id=f"turn-{turn.id}", document=self._base(company, event, document) | {"text": turn.text, "speaker_role": turn.speaker_role, "speaker_name": turn.speaker_name, "turn_id": turn.id})
            count += 1
        for slide in db.scalars(select(Slide).where(Slide.document_id == document.id)).all():
            text = "\n".join(part for part in [slide.title, slide.body_text] if part)
            self.client.index(index=self.index, id=f"slide-{slide.id}", document=self._base(company, event, document) | {"text": text, "slide_id": slide.id})
            count += 1
        for section in db.scalars(select(PressReleaseSection).where(PressReleaseSection.document_id == document.id)).all():
            self.client.index(index=self.index, id=f"section-{section.id}", document=self._base(company, event, document) | {"text": section.text, "section_type": section.section_type, "section_id": section.id})
            count += 1
        return count

    def _base(self, company, event: Event | None, document: Document) -> dict:
        return {
            "company_id": company.id if company else None,
            "company_name": company.name if company else None,
            "quarter": event.quarter if event else None,
            "fy_year": event.fy_year if event else None,
            "event_date": event.event_date.isoformat() if event else None,
            "document_type": document.document_type,
            "document_id": document.id,
        }
