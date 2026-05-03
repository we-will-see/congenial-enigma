from openai import OpenAI
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.embedding import Embedding
from app.models.event import Event
from app.models.press_release import PressReleaseSection
from app.models.slide import Slide
from app.models.turn import Turn
from app.pipeline.chunking import split_long_text, token_count


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        return []
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def build_embedding_jobs(db: Session, document_id: int) -> list[dict]:
    document, event = db.execute(select(Document, Event).join(Event, Event.id == Document.event_id).where(Document.id == document_id)).one()
    jobs = []
    for turn in db.scalars(select(Turn).where(Turn.document_id == document_id, Turn.speaker_role != "moderator")):
        if token_count(turn.text) >= 20:
            for index, chunk in enumerate(split_long_text(turn.text, max_tokens=400, overlap=0)):
                jobs.append({"turn_id": turn.id, "text": chunk, "speaker_role": turn.speaker_role, "chunk_index": index})
    for slide in db.scalars(select(Slide).where(Slide.document_id == document_id)):
        text = f"{slide.title or ''}\n{slide.body_text or ''}".strip()
        if token_count(text) >= 20:
            jobs.append({"slide_id": slide.id, "text": text, "speaker_role": "n_a", "chunk_index": slide.slide_number})
    for section in db.scalars(select(PressReleaseSection).where(PressReleaseSection.document_id == document_id)):
        if token_count(section.text) >= 20:
            for index, chunk in enumerate(split_long_text(section.text)):
                jobs.append({"section_id": section.id, "text": chunk, "speaker_role": "press_release", "chunk_index": index})
    for job in jobs:
        job.update({"company_id": event.company_id, "document_id": document.id, "document_type": document.document_type, "quarter": event.quarter, "event_date": event.event_date})
    return jobs


def generate_embeddings_for_document(db: Session, document_id: int) -> int:
    db.execute(delete(Embedding).where(Embedding.document_id == document_id))
    jobs = build_embedding_jobs(db, document_id)
    vectors = embed_texts([job["text"] for job in jobs])
    if not vectors:
        return 0
    for job, vector in zip(jobs, vectors, strict=True):
        db.add(
            Embedding(
                turn_id=job.get("turn_id"),
                slide_id=job.get("slide_id"),
                section_id=job.get("section_id"),
                company_id=job["company_id"],
                document_id=job["document_id"],
                document_type=job["document_type"],
                quarter=job["quarter"],
                event_date=job["event_date"],
                speaker_role=job["speaker_role"],
                chunk_text=job["text"],
                chunk_index=job["chunk_index"],
                embedding=vector,
            )
        )
    db.commit()
    return len(jobs)
