from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_iso


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="Untitled report")
    report_type: Mapped[str] = mapped_column(String, nullable=False, default="other")
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Sanitized enumerated failure code only — never raw exception text / PHI.
    error_code: Mapped[str | None] = mapped_column(String)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)

    uploaded_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
    analyzed_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(
        String, nullable=False, default=utcnow_iso, onupdate=utcnow_iso
    )
