from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notebook(Base):
    __tablename__ = "notebooks"
    __table_args__ = (
        UniqueConstraint("namespace_id", "name", name="uq_notebook_namespace_name"),
        Index("idx_notebooks_namespace", "namespace_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(100), default="default", nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    owner_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document_memberships = relationship("NotebookDocument", back_populates="notebook", cascade="all, delete-orphan")


class NotebookDocument(Base):
    __tablename__ = "notebook_documents"
    __table_args__ = (
        Index("idx_notebook_documents_document", "document_id"),
    )

    notebook_id: Mapped[int] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    added_by: Mapped[str | None] = mapped_column(String(200))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    notebook = relationship("Notebook", back_populates="document_memberships")
    document = relationship("Document", back_populates="notebook_memberships")
