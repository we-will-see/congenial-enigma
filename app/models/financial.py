from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Financial(Base):
    __tablename__ = "financials"
    __table_args__ = (
        UniqueConstraint("company_id", "period", "period_type"),
        Index("idx_financials_company_period", "company_id", "period"),
    )

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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancialHistory(Base):
    __tablename__ = "financials_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    financials_id: Mapped[int] = mapped_column(ForeignKey("financials.id"), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_reason: Mapped[str | None] = mapped_column(Text)
