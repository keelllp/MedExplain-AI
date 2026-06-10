"""Trend schemas (docs/04 §4.16).

A time-ordered numeric series for ONE biomarker across the caller's reports, keyed on
``canonical_name`` (D-TRENDS-PARAM) so lab synonyms collapse onto one line. Data-only: no
generated prose, no reassurance — the deterministic ``trend`` label is a directional
indicator, not a clinical judgment, so the response carries the mandatory disclaimer.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.common import DISCLAIMER, Direction, Severity


class TrendPoint(BaseModel):
    report_id: int
    point_time: str                       # COALESCE(captured_at, uploaded_at), ISO-8601
    value: float                          # numeric points only (value IS NOT NULL)
    unit: Optional[str] = None
    canonical_unit: Optional[str] = None
    # Effective reference band for the point: report-printed range, else the catalog default
    # (so the chart can shade a band and the label can be computed even when a lab omitted it).
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    severity: Optional[Severity] = None
    direction: Optional[Direction] = None


class TrendResponse(BaseModel):
    biomarker: str                        # the canonical_name queried
    display: str                          # human-readable name for the UI title
    points: list[TrendPoint]
    trend: Literal["improving", "worsening", "stable", "insufficient_data"]
    disclaimer: str = DISCLAIMER


class TrendableBiomarker(BaseModel):
    """One selectable series: a canonical_name with >= 2 numeric points for this user."""

    canonical_name: str
    display: str
    count: int
    latest_point_time: str
