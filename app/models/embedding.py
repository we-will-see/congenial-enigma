from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index("idx_embeddings_company", "company_id"),
        Index("embeddings_vector_idx", "embedding", postgresql_using="ivfflat", postgresql_with={"lists": 100}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    turn_id: Mapped[int | None] = mapped_column(ForeignKey("turns.id"))
    slide_id: Mapped[int | None] = mapped_column(ForeignKey("slides.id"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("press_release_sections.id"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quarter: Mapped[str | None] = mapped_column(String(10))
    event_date: Mapped[date | None] = mapped_column(Date)
    speaker_role: Mapped[str | None] = mapped_column(String(20))
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    model_version: Mapped[str] = mapped_column(String(50), default="text-embedding-3-small")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
