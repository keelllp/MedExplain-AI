from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_iso


class AbnormalFinding(Base):
    __tablename__ = "abnormal_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    biomarker_id: Mapped[int] = mapped_column(
        ForeignKey("biomarkers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)  # normal | abnormal
    severity: Mapped[str] = mapped_column(String, nullable=False)  # normal|mild|moderate|severe
    direction: Mapped[str] = mapped_column(String, nullable=False, default="normal")  # low|high|normal
    rule_id: Mapped[str | None] = mapped_column(String)
    # Per-biomarker plain-language explanation + citations (from the single per-report
    # LLM call, or a guarded template). Both pass the safety output guard before storage.
    explanation: Mapped[str | None] = mapped_column(String)
    citations_json: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
