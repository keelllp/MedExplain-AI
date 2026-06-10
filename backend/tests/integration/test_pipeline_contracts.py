"""Analysis-pipeline contracts: ONE LLM call per report (D-ONECALL) + guarded prose.

The LLM is invoked exactly once per analyze (for the overall summary) — NOT once per
biomarker — even when several markers are abnormal; per-finding explanations are templated.
Every explanatory string the analyze surface returns also carries the disclaimer.
"""

import uuid

import pymupdf
import pytest

from app.schemas.common import DISCLAIMER

pytestmark = pytest.mark.integration


def _auth(client) -> dict:
    email = f"pc-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pdf(*lines: str) -> bytes:
    # One marker per line: the catalog-anchored extractor takes the longest match per line.
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 22
    data = doc.tobytes()
    doc.close()
    return data


def _upload_analyze(client, headers, *lines) -> dict:
    up = client.post(
        "/api/v1/reports/upload",
        files={"file": ("multi.pdf", _pdf(*lines), "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201, up.text
    rid = up.json()["report_id"]
    assert client.post("/api/v1/reports/analyze", json={"report_id": rid}, headers=headers).status_code == 202
    return client.get(f"/api/v1/reports/{rid}", headers=headers).json()


def test_analyze_invokes_llm_exactly_once_for_multiple_abnormal_markers(client, monkeypatch):
    import app.services.llm_service as llm_service

    calls = {"n": 0}

    def spy(*args, **kwargs):
        calls["n"] += 1
        return None  # force the deterministic offline template (no network)

    monkeypatch.setattr(llm_service, "complete", spy)

    headers = _auth(client)
    # Two abnormal markers (Hb low, Glucose high) + one normal (WBC): per-biomarker calling
    # would be 2; D-ONECALL requires exactly 1 (the overall summary).
    detail = _upload_analyze(
        client, headers, "Hemoglobin 9.1 g/dL", "Glucose 142 mg/dL", "WBC 7.2 10^3/uL"
    )
    assert detail["status"] == "analyzed"
    abnormal = [f for f in detail["findings"] if f["status"] == "abnormal"]
    assert len(abnormal) >= 2  # guard: the fixture really has multiple abnormal markers
    assert calls["n"] == 1, f"expected ONE LLM call per report, got {calls['n']}"


def test_every_analyze_explanation_carries_the_disclaimer(client):
    headers = _auth(client)
    detail = _upload_analyze(client, headers, "Hemoglobin 9.1 g/dL", "Glucose 142 mg/dL")
    assert detail["disclaimer"] == DISCLAIMER
    assert DISCLAIMER in detail["summary"]["summary_text"]
    for f in detail["findings"]:
        if f["explanation"]:
            assert DISCLAIMER in f["explanation"], f"finding {f['id']} explanation missing disclaimer"
