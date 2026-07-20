from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_event", "event_id"),
        Index("idx_documents_type", "document_type"),
        Index("idx_documents_status", "extraction_status"),
        Index("idx_documents_file_hash", "file_hash"),
        Index("idx_documents_source_type", "source_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(50), default="bse", nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    rights_scope: Mapped[str] = mapped_column(String(50), default="public", nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String(200))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)
    pdf_type: Mapped[str | None] = mapped_column(String(20))
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_flags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event = relationship("Event", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    notebook_memberships = relationship("NotebookDocument", back_populates="document", cascade="all, delete-orphan")
