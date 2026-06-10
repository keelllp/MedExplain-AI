"""Biomarker / finding / citation output schemas (docs/04 §3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Direction, Severity


class CitationOut(BaseModel):
    n: int
    doc_title: str
    section: str | None = None
    source_path: str | None = None


class BiomarkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_name: str
    canonical_name: str | None = None
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    canonical_unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    reference_range_text: str | None = None
    captured_at: str | None = None


class AbnormalFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    biomarker_id: int
    status: str
    severity: Severity
    direction: Direction
    rule_id: str | None = None
    explanation: str | None = None  # populated in Phase 5 (guarded prose)
    citations: list[CitationOut] = []
