from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_iso


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    # gemini | ollama | offline_template — drives the UI "offline" badge.
    generation_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="offline_template"
    )
    model_used: Mapped[str] = mapped_column(String, nullable=False)  # free-text provenance
    generated_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
