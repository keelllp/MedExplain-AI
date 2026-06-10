"""Trend assembly + the deterministic improving/worsening/stable label (no LLM).

The label is computed purely from the series relative to the reference band: the distance
the first vs. the last numeric point sits OUTSIDE its band. Moving toward in-range →
improving; away → worsening; negligible change → stable; < 2 points → insufficient_data.
This is a descriptive directional indicator, NOT a clinical judgment (docs/04 §4.16), and
the response always carries the disclaimer. Reference bounds fall back to the catalog
default when a report didn't print a range, so the label/band work for any lab.
"""

from __future__ import annotations

from app.schemas.trend import TrendPoint
from app.services.catalog import load_catalog

_NEGLIGIBLE_FRAC = 0.05  # change within 5% of the band width counts as "stable"


def display_name(canonical_name: str) -> str:
    return load_catalog().get(canonical_name, {}).get("display") or canonical_name.replace("_", " ")


def _out_of_range_distance(value: float, low: float | None, high: float | None) -> float:
    """How far the value sits OUTSIDE [low, high]; 0 when in range (or no bound applies)."""
    if low is not None and value < low:
        return low - value
    if high is not None and value > high:
        return value - high
    return 0.0


def _trend_label(points: list[TrendPoint]) -> str:
    if len(points) < 2:
        return "insufficient_data"
    first, last = points[0], points[-1]
    d0 = _out_of_range_distance(first.value, first.reference_low, first.reference_high)
    d1 = _out_of_range_distance(last.value, last.reference_low, last.reference_high)

    if last.reference_low is not None and last.reference_high is not None and last.reference_high > last.reference_low:
        scale = last.reference_high - last.reference_low
    else:
        scale = max(abs(first.value), abs(last.value), 1.0)
    eps = scale * _NEGLIGIBLE_FRAC

    delta = d1 - d0  # negative = closer to in-range now (improving)
    if abs(delta) <= eps:
        return "stable"
    return "improving" if delta < 0 else "worsening"


def build(canonical_name: str, rows) -> tuple[str, list[TrendPoint], str]:
    """Map DB rows → TrendPoints (with catalog-fallback reference band) + the trend label."""
    entry = load_catalog().get(canonical_name, {})
    default_low, default_high = entry.get("default_low"), entry.get("default_high")

    points: list[TrendPoint] = []
    for r in rows:
        points.append(
            TrendPoint(
                report_id=r.report_id,
                point_time=r.point_time,
                value=r.value,
                unit=r.unit,
                canonical_unit=r.canonical_unit,
                reference_low=r.reference_low if r.reference_low is not None else default_low,
                reference_high=r.reference_high if r.reference_high is not None else default_high,
                severity=r.severity,
                direction=r.direction,
            )
        )
    return display_name(canonical_name), points, _trend_label(points)
