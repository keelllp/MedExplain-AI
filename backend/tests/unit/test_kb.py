"""Unit tests for deterministic KB retrieval."""

import pytest

from app.services import kb

pytestmark = pytest.mark.unit


def test_retrieve_low_returns_what_and_low_sections():
    chunks = kb.retrieve("hemoglobin", "low")
    assert len(chunks) == 2
    assert chunks[0].doc_title == "Hemoglobin"
    assert "what it measures" in chunks[0].section.lower()
    assert "low" in chunks[1].section.lower()
    assert chunks[0].source_path.endswith("hemoglobin.md")


def test_retrieve_high():
    chunks = kb.retrieve("glucose", "high")
    assert any("high" in c.section.lower() for c in chunks)
    assert all(c.doc_title.startswith("Glucose") for c in chunks)


def test_aliased_canonical_maps_to_shared_doc():
    chunks = kb.retrieve("hematocrit", "low")  # maps to hemoglobin.md
    assert chunks and chunks[0].source_path.endswith("hemoglobin.md")


def test_thyroid_markers_map_to_thyroid_doc():
    for marker in ("tsh", "free_t4", "free_t3"):
        chunks = kb.retrieve(marker, "high")
        assert chunks and chunks[0].source_path.endswith("thyroid.md")


def test_unknown_marker_returns_empty():
    assert kb.retrieve("not_a_marker", "low") == []
    assert kb.retrieve(None, None) == []


def test_normal_direction_returns_only_what_it_measures():
    chunks = kb.retrieve("hemoglobin", "normal")
    assert len(chunks) == 1
    assert "what it measures" in chunks[0].section.lower()
