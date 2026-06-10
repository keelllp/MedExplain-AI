"""Unit tests for explanation generation (offline template + guarded LLM path)."""

from types import SimpleNamespace

import pytest

from app.safety import DISCLAIMER
from app.services import explanation_service

pytestmark = pytest.mark.unit

_USER = SimpleNamespace(llm_mode="offline", gemini_consent=0)


def _bm(**kw):
    base = dict(
        id=1, canonical_name="hemoglobin", test_name="Hb", value=9.1, value_text=None,
        unit="g/dL", canonical_unit="g/dL", reference_low=13.0, reference_high=17.0,
        reference_range_text="13.0-17.0",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _finding(**kw):
    base = dict(biomarker_id=1, status="abnormal", severity="moderate", direction="low")
    base.update(kw)
    return SimpleNamespace(**base)


def test_offline_template_generation(monkeypatch):
    monkeypatch.setattr(explanation_service.llm_service, "complete", lambda *a, **k: None)
    res = explanation_service.generate(SimpleNamespace(id=1), [_bm()], [_finding()], _USER)

    assert res["generation_mode"] == "offline_template"
    assert DISCLAIMER in res["overall_summary"]
    assert "Hemoglobin" in res["overall_summary"]

    per = res["per_finding"][1]
    assert DISCLAIMER in per["explanation"]
    assert "carries oxygen" in per["explanation"].lower()       # grounded in the KB
    assert "below the reference range" in per["explanation"].lower()
    assert per["citations"] and per["citations"][0]["doc_title"] == "Hemoglobin"

    texts = [q["question_text"] for q in res["doctor_questions"]]
    assert any("causing my low Hemoglobin" in t for t in texts)
    assert any(q["category"] == "follow-up" for q in res["doctor_questions"])


def test_llm_summary_is_guarded(monkeypatch):
    # A misbehaving LLM returns NATURAL prohibited phrasings → all must be scrubbed.
    monkeypatch.setattr(
        explanation_service.llm_service,
        "complete",
        lambda *a, **k: (
            "Your results are consistent with anemia. Your numbers look good and this is "
            "nothing serious. Consider taking an iron supplement.",
            "ollama/gemma3:4b",
        ),
    )
    res = explanation_service.generate(SimpleNamespace(id=1), [_bm()], [_finding()], _USER)
    summary = res["overall_summary"].lower()
    assert res["generation_mode"] == "ollama"
    assert "consistent with anemia" not in summary
    assert "nothing serious" not in summary
    assert "consider taking" not in summary
    assert DISCLAIMER in res["overall_summary"]


def test_qualitative_abnormal_explanation(monkeypatch):
    monkeypatch.setattr(explanation_service.llm_service, "complete", lambda *a, **k: None)
    bm = SimpleNamespace(
        id=1, canonical_name="urine_protein", test_name="Urine Protein", value=None,
        value_text="Positive", unit=None, canonical_unit=None,
        reference_low=None, reference_high=None, reference_range_text="Negative",
    )
    finding = SimpleNamespace(biomarker_id=1, status="abnormal", severity="mild", direction="normal")
    res = explanation_service.generate(SimpleNamespace(id=1), [bm], [finding], _USER)
    explanation = res["per_finding"][1]["explanation"]
    assert "a result of positive is unexpected" in explanation.lower()
    assert "(the reference range)" not in explanation.lower()  # no ungrammatical numeric range
    assert DISCLAIMER in explanation


def test_normal_finding_explanation(monkeypatch):
    monkeypatch.setattr(explanation_service.llm_service, "complete", lambda *a, **k: None)
    bm = _bm(value=14.0)
    finding = _finding(status="normal", severity="normal", direction="normal")
    res = explanation_service.generate(SimpleNamespace(id=1), [bm], [finding], _USER)
    per = res["per_finding"][1]
    assert "within the reference range" in per["explanation"].lower()
    assert DISCLAIMER in per["explanation"]
    # no abnormal findings → summary says all within range
    assert "within their reference ranges" in res["overall_summary"].lower()
