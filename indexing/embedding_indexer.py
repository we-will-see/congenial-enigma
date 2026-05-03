from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.db.models import Document, Embedding, Event, PressReleaseSection, Slide, Turn
from services.embedding_service import EmbeddingGenerator


class EmbeddingIndexer:
    def __init__(self) -> None:
        self.generator = EmbeddingGenerator()

    def index_document_content(self, db: Session, document: Document) -> int:
        db.execute(delete(Embedding).where(Embedding.document_id == document.id))
        event = db.scalar(select(Event).where(Event.id == document.event_id))
        chunks: list[Embedding] = []
        for turn in db.scalars(select(Turn).where(Turn.document_id == document.id, Turn.word_count >= 20, Turn.speaker_role != "moderator")).all():
            chunks.append(self._embedding(document, event, turn.text, len(chunks), turn_id=turn.id, speaker_role=turn.speaker_role))
        for slide in db.scalars(select(Slide).where(Slide.document_id == document.id)).all():
            text = "\n".join(part for part in [slide.title, slide.body_text] if part)
            if len(text.split()) >= 20:
                chunks.append(self._embedding(document, event, text, len(chunks), slide_id=slide.id))
        for section in db.scalars(select(PressReleaseSection).where(PressReleaseSection.document_id == document.id)).all():
            for text in self._split_section(section.text):
                chunks.append(self._embedding(document, event, text, len(chunks), section_id=section.id, speaker_role="press_release"))
        db.add_all(chunks)
        db.commit()
        return len(chunks)

    def _embedding(self, document: Document, event: Event | None, text: str, index: int, **refs) -> Embedding:
        return Embedding(
            document_id=document.id,
            company_id=event.company_id if event else 0,
            document_type=document.document_type,
            quarter=event.quarter if event else None,
            event_date=event.event_date if event else None,
            chunk_text=text,
            chunk_index=index,
            embedding=self.generator.embed(text),
            **refs,
        )

    def _split_section(self, text: str) -> list[str]:
        words = text.split()
        if len(words) <= 400:
            return [text] if len(words) >= 20 else []
        chunks: list[str] = []
        start = 0
        while start < len(words):
            chunk = words[start : start + 400]
            if len(chunk) >= 20:
                chunks.append(" ".join(chunk))
            start += 350
        return chunks
