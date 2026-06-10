from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_iso


class Biomarker(Base):
    __tablename__ = "biomarkers"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    test_name: Mapped[str] = mapped_column(String, nullable=False)  # raw printed name
    canonical_name: Mapped[str | None] = mapped_column(String)  # normalized key (trends/KB)
    value: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    canonical_unit: Mapped[str | None] = mapped_column(String)
    reference_low: Mapped[float | None] = mapped_column(Float)
    reference_high: Mapped[float | None] = mapped_column(Float)
    reference_range_text: Mapped[str | None] = mapped_column(String)
    captured_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
