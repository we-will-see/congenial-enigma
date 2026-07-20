import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.pipeline.embedding_service import embed_texts


@dataclass(frozen=True)
class ChunkSpec:
    ordinal: int
    page_start: int
    page_end: int
    text: str
    text_hash: str


def build_page_chunk_specs(
    pages: list[tuple[int, str]],
    max_words: int = 350,
    overlap_words: int = 50,
) -> list[ChunkSpec]:
    """Split each page independently so every result has an exact page citation."""
    if max_words < 1:
        raise ValueError("max_words must be positive")
    if overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("overlap_words must be between zero and max_words - 1")

    specs: list[ChunkSpec] = []
    ordinal = 0
    for page_number, page_text in pages:
        words = page_text.split()
        start = 0
        while start < len(words):
            end = min(len(words), start + max_words)
            text = " ".join(words[start:end]).strip()
            if text:
                specs.append(
                    ChunkSpec(
                        ordinal=ordinal,
                        page_start=page_number,
                        page_end=page_number,
                        text=text,
                        text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    )
                )
                ordinal += 1
            if end == len(words):
                break
            start = end - overlap_words
    return specs


def rebuild_chunks_for_document(db: Session, document_id: int, embed: bool = True) -> int:
    document = db.get(Document, document_id)
    if not document:
        raise ValueError(f"document {document_id} not found")

    pages = list(
        db.execute(
            select(DocumentPage.page_number, DocumentPage.text)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
    )
    specs = build_page_chunk_specs([(row.page_number, row.text) for row in pages])
    db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    chunks = [
        Chunk(
            document_id=document_id,
            ordinal=spec.ordinal,
            page_start=spec.page_start,
            page_end=spec.page_end,
            section_type=document.document_type,
            text=spec.text,
            text_hash=spec.text_hash,
        )
        for spec in specs
    ]
    db.add_all(chunks)
    db.flush()

    if embed and chunks:
        vectors = embed_texts([chunk.text for chunk in chunks])
        if vectors:
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_model = settings.embedding_model
    return len(chunks)
