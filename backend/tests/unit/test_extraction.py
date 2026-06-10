"""Unit tests for catalog-anchored biomarker extraction + reference-range parsing."""

import pytest

from app.services.extraction_service import _parse_range, extract

pytestmark = pytest.mark.unit


def _by_name(rows):
    return {r.canonical_name: r for r in rows}


def test_numeric_line_with_range():
    hb = _by_name(extract("Hemoglobin 9.1 g/dL 13.0-17.0", None))["hemoglobin"]
    assert hb.value == 9.1
    assert hb.reference_low == 13.0 and hb.reference_high == 17.0
    assert hb.unit == "g/dL" and hb.canonical_unit == "g/dL"


def test_one_sided_range_and_longest_alias():
    c = _by_name(extract("Total Cholesterol 210 mg/dL <200", None))["cholesterol_total"]
    assert c.value == 210.0
    assert c.reference_low is None and c.reference_high == 200.0


def test_abbreviation_alias():
    assert _by_name(extract("Hb 13.5 g/dL", None)).get("hemoglobin") is not None


def test_qualitative_result():
    up = _by_name(extract("Urine Protein  Positive  (Negative)", None)).get("urine_protein")
    assert up is not None
    assert up.value is None and up.value_text.lower() == "positive"


def test_extracts_from_tables():
    tables = [{"page": 0, "rows": [["WBC", "7.2", "10^3/uL", "4.0-11.0"]]}]
    w = _by_name(extract("", tables)).get("wbc")
    assert w is not None and w.value == 7.2
    assert w.reference_low == 4.0 and w.reference_high == 11.0


def test_no_known_marker_returns_empty():
    assert extract("Patient: John Doe   Collected 2026-06-01   General lab report", None) == []


def test_hba1c_not_misread_as_hemoglobin():
    names = _by_name(extract("HbA1c 5.4 %", None))
    assert "hba1c" in names and "hemoglobin" not in names


def test_parse_range_forms():
    assert _parse_range("13.0-17.0")[:2] == (13.0, 17.0)
    assert _parse_range("< 200")[:2] == (None, 200.0)
    assert _parse_range(">= 40")[:2] == (40.0, None)
    assert _parse_range("up to 5.0")[:2] == (None, 5.0)
    assert _parse_range("no range here")[:2] == (None, None)


def test_date_after_value_is_not_a_range():
    hb = _by_name(extract("Hemoglobin 13.5 g/dL 2026-06-01", None))["hemoglobin"]
    assert hb.value == 13.5
    assert hb.reference_low is None and hb.reference_high is None


def test_range_only_row_yields_no_biomarker():
    # a range with no result printed must NOT fabricate a value (false "normal")
    assert extract("TSH 0.4-4.0", None) == []


def test_range_printed_before_value():
    hb = _by_name(extract("Hemoglobin 13.0-17.0 g/dL 9.1", None))["hemoglobin"]
    assert hb.value == 9.1  # not 13.0 (the range low)
    assert hb.reference_low == 13.0 and hb.reference_high == 17.0


def test_thousands_separator_value():
    plt = _by_name(extract("Platelets 250,000 /cumm 150000-400000", None))["platelets"]
    assert plt.value == 250000.0


def test_value_not_taken_from_digit_bearing_unit():
    rbc = _by_name(extract("RBC count 10^6/uL 5.1 4.2-5.9", None))["rbc"]
    assert rbc.value == 5.1  # not 10 (from the 10^6 unit)
