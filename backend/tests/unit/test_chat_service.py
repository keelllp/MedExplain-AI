"""Unit tests for chat_service — the pure retrieval + guard logic (no DB, LLM stubbed)."""

from types import SimpleNamespace

import pytest

from app.schemas.common import DISCLAIMER
from app.services import chat_service

pytestmark = pytest.mark.unit


def _user(mode="offline"):
    return SimpleNamespace(llm_mode=mode, gemini_consent=0)


def _bm(id, canonical_name, value=None, unit=None, low=None, high=None, value_text=None):
    return SimpleNamespace(
        id=id, canonical_name=canonical_name, value=value, value_text=value_text,
        unit=unit, canonical_unit=unit, reference_low=low, reference_high=high,
        reference_range_text=None,
    )


def _finding(biomarker_id, status="abnormal", severity="moderate", direction="low"):
    return SimpleNamespace(
        biomarker_id=biomarker_id, status=status, severity=severity, direction=direction
    )


def _answer(**kw):
    base = dict(message="", report_id=None, biomarkers=[], findings=[], history=[], user=_user())
    base.update(kw)
    return chat_service.answer_question(**base)


# --- marker resolution -------------------------------------------------------
def test_resolve_markers_matches_aliases_and_canonicals():
    assert "hemoglobin" in chat_service._resolve_markers("what does my Hb mean?")
    assert "glucose" in chat_service._resolve_markers("explain fasting blood sugar")
    assert chat_service._resolve_markers("what is the weather today") == []


# --- input guard / refusals --------------------------------------------------
def test_refusal_short_circuits_with_disclaimer_and_no_citations(monkeypatch):
    # Even if an LLM were available, a refused input must not reach it.
    monkeypatch.setattr(
        chat_service.llm_service, "complete", lambda *a, **k: ("SHOULD NOT APPEAR", "ollama/x")
    )
    out = _answer(message="What disease do I have?")
    assert out["refused"] is True
    assert out["citations"] == []
    assert out["generation_mode"] == "offline_template"
    assert "SHOULD NOT APPEAR" not in out["answer"]
    assert DISCLAIMER in out["answer"]


# --- offline floor (no LLM) --------------------------------------------------
def test_offline_general_named_marker_has_citation(monkeypatch):
    monkeypatch.setattr(chat_service.llm_service, "complete", lambda *a, **k: None)
    out = _answer(message="What does hemoglobin measure?")
    assert out["refused"] is False
    assert out["generation_mode"] == "offline_template"
    assert DISCLAIMER in out["answer"]
    assert out["citations"] and out["citations"][0]["doc"] == "Hemoglobin"
    assert out["citations"][0]["chunk_id"].startswith("hemoglobin#")
    assert out["citations"][0]["score"] == 1.0


def test_offline_unknown_topic_is_safe_and_uncited(monkeypatch):
    monkeypatch.setattr(chat_service.llm_service, "complete", lambda *a, **k: None)
    out = _answer(message="What is the weather like today?")
    assert out["citations"] == []
    assert DISCLAIMER in out["answer"]
    assert len(out["answer"]) > len(DISCLAIMER)  # a real fallback body, not just the disclaimer


def test_report_scoped_filters_to_report_markers(monkeypatch):
    monkeypatch.setattr(chat_service.llm_service, "complete", lambda *a, **k: None)
    bms = [_bm(1, "hemoglobin", value=9.1, unit="g/dL", low=12.0, high=17.5)]
    fnds = [_finding(1, direction="low")]
    out = _answer(
        message="can you explain my results?",  # names no marker → falls back to abnormal markers
        report_id=42, biomarkers=bms, findings=fnds,
    )
    assert any(c["doc"] == "Hemoglobin" for c in out["citations"])


# --- LLM path is guarded -----------------------------------------------------
def test_llm_answer_passes_through_output_guard(monkeypatch):
    # A model that emits a prohibited diagnosis must be scrubbed before return.
    monkeypatch.setattr(
        chat_service.llm_service,
        "complete",
        lambda *a, **k: ("This is consistent with anemia. Hemoglobin carries oxygen.", "ollama/gemma3:4b"),
    )
    out = _answer(message="What does hemoglobin measure?")
    assert out["generation_mode"] == "ollama"
    assert "consistent with anemia" not in out["answer"].lower()  # scrubbed
    assert "carries oxygen" in out["answer"].lower()              # educational sentence kept
    assert DISCLAIMER in out["answer"]


def test_allow_llm_false_forces_offline(monkeypatch):
    monkeypatch.setattr(
        chat_service.llm_service, "complete", lambda *a, **k: ("LLM TEXT", "ollama/x")
    )
    out = _answer(message="What does hemoglobin measure?", allow_llm=False)
    assert out["generation_mode"] == "offline_template"
    assert "LLM TEXT" not in out["answer"]


def test_offline_user_never_calls_gemini(monkeypatch):
    seen = {}

    def fake_complete(system, user, *, llm_mode, gemini_consent=False):
        seen["llm_mode"] = llm_mode
        return None

    monkeypatch.setattr(chat_service.llm_service, "complete", fake_complete)
    _answer(message="What does hemoglobin measure?", user=_user("offline"))
    assert seen["llm_mode"] == "offline"  # router resolves provider from this (no Gemini)
