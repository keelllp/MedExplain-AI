"""Deterministic abnormality rule engine (no LLM).

For each biomarker it compares the value against a reference range — preferring the
range PRINTED on the report, falling back to the catalog default — and assigns
status / severity / direction / rule_id. Qualitative results are matched against an
expected set. Severity is a generic percentage-beyond-bound band (educational, not
diagnostic). Biomarkers that can't be assessed (no range, or unknown marker) get NO
finding rather than a misleading "normal" (the safety doc forbids false reassurance).

It emits NO user-facing prose in Phase 4 — explanation/citations are filled in Phase 5
once the safety output guard exists.
"""

from __future__ import annotations

from app.services.catalog import load_catalog

_MILD_PCT = 10.0
_MODERATE_PCT = 30.0


def evaluate(biomarker) -> dict | None:
    """Return a finding dict (status/severity/direction/rule_id) or None if not assessable."""
    catalog = load_catalog()
    entry = catalog.get(biomarker.canonical_name)
    if entry is None:
        return None
    if entry.get("type") == "qualitative":
        return _evaluate_qualitative(biomarker, entry)
    return _evaluate_numeric(biomarker, entry)


def _evaluate_numeric(biomarker, entry) -> dict | None:
    if biomarker.value is None:
        return None
    low = biomarker.reference_low if biomarker.reference_low is not None else entry.get("default_low")
    high = biomarker.reference_high if biomarker.reference_high is not None else entry.get("default_high")
    if low is None and high is None:
        return None  # not assessable

    key = biomarker.canonical_name.upper()
    value = biomarker.value
    if low is not None and value < low:
        return _finding("abnormal", _band(_pct(low - value, low)), "low", f"{key}_LOW")
    if high is not None and value > high:
        return _finding("abnormal", _band(_pct(value - high, high)), "high", f"{key}_HIGH")
    return _finding("normal", "normal", "normal", f"{key}_NORMAL")


def _evaluate_qualitative(biomarker, entry) -> dict | None:
    if not biomarker.value_text:
        return None
    expected = {e.lower() for e in entry.get("expected", [])}
    if not expected:
        return None
    key = biomarker.canonical_name.upper()
    if biomarker.value_text.strip().lower() in expected:
        return _finding("normal", "normal", "normal", f"{key}_EXPECTED")
    severity = entry.get("abnormal_severity", "mild")
    if severity not in ("mild", "moderate", "severe"):
        severity = "mild"
    return _finding("abnormal", severity, "normal", f"{key}_UNEXPECTED")


def _pct(delta: float, bound: float) -> float:
    # Degenerate 0-bound: the % band isn't meaningful, but status/direction are still
    # correct; scale by 1.0 to avoid div-by-zero. round() absorbs float noise at the
    # exact band boundaries (e.g. 30.0000000004%).
    base = abs(bound) or 1.0
    return round((delta / base) * 100.0, 6)


def _band(pct: float) -> str:
    if pct <= _MILD_PCT:
        return "mild"
    if pct <= _MODERATE_PCT:
        return "moderate"
    return "severe"


def _finding(status: str, severity: str, direction: str, rule_id: str) -> dict:
    return {"status": status, "severity": severity, "direction": direction, "rule_id": rule_id}
