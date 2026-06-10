"""Integration tests for the trend surface (Phase 8). Offline; native-text PDFs only."""

import uuid

import pymupdf
import pytest

from app.schemas.common import DISCLAIMER

pytestmark = pytest.mark.integration


def _auth_headers(client) -> dict:
    email = f"t-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _analyzed(client, headers, text: str) -> int:
    up = client.post(
        "/api/v1/reports/upload",
        files={"file": ("r.pdf", _pdf(text), "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201, up.text
    rid = up.json()["report_id"]
    an = client.post("/api/v1/reports/analyze", json={"report_id": rid}, headers=headers)
    assert an.status_code == 202, an.text
    assert client.get(f"/api/v1/reports/{rid}", headers=headers).json()["status"] == "analyzed"
    return rid


def test_trend_series_ordered_with_band_and_label(client):
    headers = _auth_headers(client)
    r1 = _analyzed(client, headers, "Hemoglobin 9.1 g/dL   Glucose 88 mg/dL")
    r2 = _analyzed(client, headers, "Hgb 11.5 g/dL")  # synonym → same canonical series

    data = client.get("/api/v1/trends?biomarker=hemoglobin", headers=headers).json()
    assert data["biomarker"] == "hemoglobin"
    assert data["display"] == "Hemoglobin"
    assert data["disclaimer"] == DISCLAIMER

    points = data["points"]
    assert [p["report_id"] for p in points] == [r1, r2]  # oldest first
    assert [p["value"] for p in points] == [9.1, 11.5]
    # band filled from catalog default (the PDFs print no range)
    assert points[0]["reference_low"] == 12.0 and points[0]["reference_high"] == 17.5
    assert all(p["direction"] == "low" for p in points)  # both below range
    assert data["trend"] == "improving"  # 9.1 → 11.5 moves toward the band


def test_selector_lists_only_biomarkers_with_two_points(client):
    headers = _auth_headers(client)
    _analyzed(client, headers, "Hemoglobin 9.1 g/dL   Glucose 88 mg/dL")
    _analyzed(client, headers, "Hgb 11.5 g/dL")

    items = client.get("/api/v1/trends/biomarkers", headers=headers).json()
    names = {i["canonical_name"]: i for i in items}
    assert "hemoglobin" in names                # 2 numeric points → trendable
    assert names["hemoglobin"]["count"] == 2
    assert names["hemoglobin"]["display"] == "Hemoglobin"
    assert "glucose" not in names               # only 1 point → not listed


def test_unknown_biomarker_returns_empty_insufficient(client):
    headers = _auth_headers(client)
    data = client.get("/api/v1/trends?biomarker=ferritin", headers=headers).json()
    assert data["points"] == []
    assert data["trend"] == "insufficient_data"


def test_missing_param_is_422(client):
    headers = _auth_headers(client)
    assert client.get("/api/v1/trends", headers=headers).status_code == 422


def test_requires_auth(client):
    assert client.get("/api/v1/trends?biomarker=hemoglobin").status_code == 401
    assert client.get("/api/v1/trends/biomarkers").status_code == 401


def test_owner_scoping(client):
    owner = _auth_headers(client)
    _analyzed(client, owner, "Hemoglobin 9.1 g/dL")
    _analyzed(client, owner, "Hgb 11.5 g/dL")
    other = _auth_headers(client)

    # Another user sees none of the owner's series.
    assert client.get("/api/v1/trends/biomarkers", headers=other).json() == []
    assert client.get("/api/v1/trends?biomarker=hemoglobin", headers=other).json()["points"] == []
