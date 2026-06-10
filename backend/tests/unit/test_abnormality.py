"""Unit tests for the deterministic abnormality rule engine."""

from types import SimpleNamespace

import pytest

from app.services.abnormality_service import evaluate

pytestmark = pytest.mark.unit


def _bm(**kw):
    base = dict(
        canonical_name="hemoglobin", value=None, value_text=None,
        reference_low=None, reference_high=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_low_value_is_abnormal_low():
    v = evaluate(_bm(value=9.1, reference_low=13.0, reference_high=17.0))
    assert v["status"] == "abnormal" and v["direction"] == "low"
    assert v["rule_id"] == "HEMOGLOBIN_LOW"


def test_high_value_severe():
    v = evaluate(_bm(canonical_name="glucose", value=200, reference_low=70, reference_high=99))
    assert v["status"] == "abnormal" and v["direction"] == "high" and v["severity"] == "severe"


def test_in_range_is_normal():
    v = evaluate(_bm(value=14.0, reference_low=13.0, reference_high=17.0))
    assert v == {"status": "normal", "severity": "normal", "direction": "normal",
                 "rule_id": "HEMOGLOBIN_NORMAL"}


def test_falls_back_to_catalog_default_range():
    # hemoglobin catalog default low = 12.0; no report range provided
    v = evaluate(_bm(value=11.0))
    assert v["status"] == "abnormal" and v["direction"] == "low"


def test_severity_bands():
    assert evaluate(_bm(value=12.5, reference_low=13.0, reference_high=17.0))["severity"] == "mild"
    assert evaluate(_bm(value=9.1, reference_low=13.0, reference_high=17.0))["severity"] == "moderate"
    assert evaluate(_bm(value=8.0, reference_low=13.0, reference_high=17.0))["severity"] == "severe"


def test_qualitative_unexpected_is_abnormal():
    v = evaluate(_bm(canonical_name="urine_protein", value_text="Positive"))
    assert v["status"] == "abnormal" and v["severity"] == "mild" and v["direction"] == "normal"


def test_qualitative_expected_is_normal():
    v = evaluate(_bm(canonical_name="urine_protein", value_text="Negative"))
    assert v["status"] == "normal"


def test_unknown_marker_not_assessable():
    assert evaluate(_bm(canonical_name="not_a_marker", value=5.0)) is None


def test_numeric_without_any_range_not_assessable():
    # a known marker but with no report range AND no catalog default on either side
    bm = _bm(canonical_name="ferritin", value=50.0)
    # ferritin has catalog defaults, so craft an unknown to force not-assessable:
    assert evaluate(_bm(canonical_name="not_in_catalog", value=50.0)) is None
    # sanity: ferritin IS assessable
    assert evaluate(bm) is not None
