from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (
        UniqueConstraint("document_id", "turn_index"),
        Index("idx_turns_document", "document_id"),
        Index("idx_turns_role", "speaker_role"),
    )

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
