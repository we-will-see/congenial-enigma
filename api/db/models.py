from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scrip_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    sector: Mapped[str | None] = mapped_column(String(100))
    sub_sector: Mapped[str | None] = mapped_column(String(100))
    bse_id: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list["Event"]] = relationship(back_populates="company")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    bse_filing_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quarter: Mapped[str | None] = mapped_column(String(10))
    fy_year: Mapped[int | None] = mapped_column(Integer)
    filing_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="events")
    documents: Mapped[list["Document"]] = relationship(back_populates="event")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bse_url: Mapped[str | None] = mapped_column(Text)
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

    event: Mapped[Event] = relationship(back_populates="documents")
    turns: Mapped[list["Turn"]] = relationship(back_populates="document")
    slides: Mapped[list["Slide"]] = relationship(back_populates="document")
    sections: Mapped[list["PressReleaseSection"]] = relationship(back_populates="document")


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("document_id", "turn_index"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_raw: Mapped[str | None] = mapped_column(Text)
    speaker_name: Mapped[str | None] = mapped_column(String(200))
    speaker_role: Mapped[str] = mapped_column(String(20), nullable=False)
    speaker_org: Mapped[str | None] = mapped_column(String(200))
    speaker_title: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="turns")


class Slide(Base):
    __tablename__ = "slides"
    __table_args__ = (UniqueConstraint("document_id", "slide_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    slide_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="slides")


class PressReleaseSection(Base):
    __tablename__ = "press_release_sections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    section_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section_order: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="sections")


class ManagementChange(Base):
    __tablename__ = "management_changes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    role_category: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    din: Mapped[str | None] = mapped_column(String(20))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Financial(Base):
    __tablename__ = "financials"
    __table_args__ = (UniqueConstraint("company_id", "period", "period_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ebitda_margin: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    da: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ebit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    finance_costs: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pbt: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pat: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    eps_basic: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    eps_diluted: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    shares_cr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    currency: Mapped[str] = mapped_column(String(5), default="INR")
    unit: Mapped[str] = mapped_column(String(20), default="Crores")
    restated: Mapped[bool] = mapped_column(Boolean, default=False)
    restatement_note: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    quality_flags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"

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


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[Any]] = mapped_column(JSON, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class FinancialHistory(Base):
    __tablename__ = "financials_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    financials_id: Mapped[int] = mapped_column(ForeignKey("financials.id"), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_reason: Mapped[str | None] = mapped_column(Text)
