"""Unit tests for the deterministic trend label (no DB, no LLM)."""

import pytest

from app.schemas.trend import TrendPoint
from app.services import trend_service

pytestmark = pytest.mark.unit


def _pt(value, low=12.0, high=17.5, t="2026-01-01T00:00:00Z"):
    return TrendPoint(report_id=1, point_time=t, value=value, reference_low=low, reference_high=high)


def test_insufficient_data_under_two_points():
    assert trend_service._trend_label([]) == "insufficient_data"
    assert trend_service._trend_label([_pt(9.0)]) == "insufficient_data"


def test_improving_when_moving_toward_range():
    # 9.1 (2.9 below) -> 11.5 (0.5 below): distance shrank → improving
    assert trend_service._trend_label([_pt(9.1), _pt(11.5)]) == "improving"


def test_worsening_when_moving_away_from_range():
    # 13.0 (in range) -> 9.0 (3.0 below): distance grew → worsening
    assert trend_service._trend_label([_pt(13.0), _pt(9.0)]) == "worsening"


def test_stable_when_both_in_range():
    assert trend_service._trend_label([_pt(13.0), _pt(14.5)]) == "stable"


def test_stable_when_change_is_negligible():
    # both ~2.9 below: change well under 5% of the 5.5-wide band → stable
    assert trend_service._trend_label([_pt(9.1), _pt(9.0)]) == "stable"


def test_build_fills_reference_band_from_catalog_default():
    # Rows with no printed range still get a band from the catalog so the label/chart work.
    rows = [
        _Row(report_id=1, point_time="2026-01-01T00:00:00Z", value=9.1, reference_low=None, reference_high=None),
        _Row(report_id=2, point_time="2026-02-01T00:00:00Z", value=11.5, reference_low=None, reference_high=None),
    ]
    display, points, trend = trend_service.build("hemoglobin", rows)
    assert display == "Hemoglobin"
    assert points[0].reference_low == 12.0 and points[0].reference_high == 17.5  # catalog default
    assert trend == "improving"


class _Row:
    """Stand-in for a SQLAlchemy Row with the labeled columns trend_points returns."""

    def __init__(self, **kw):
        self.unit = self.canonical_unit = self.severity = self.direction = None
        self.__dict__.update(kw)
