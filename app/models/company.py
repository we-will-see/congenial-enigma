from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events = relationship("Event", back_populates="company")
