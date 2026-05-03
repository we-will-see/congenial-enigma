from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ManagementChange(Base):
    __tablename__ = "management_changes"
    __table_args__ = (
        Index("idx_mgmt_changes_company", "company_id"),
        Index("idx_mgmt_changes_date", "filing_date"),
        UniqueConstraint("company_id", "person_name", "change_type", "effective_date", name="uq_mgmt_change_identity"),
    )

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
