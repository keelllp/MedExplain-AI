"""Integration tests for the PDF export surface (Phase 10)."""

import uuid

import pymupdf
import pytest

pytestmark = pytest.mark.integration


def _auth(client) -> dict:
    email = f"x-{uuid.uuid4().hex[:10]}@example.com"
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


def _upload(client, headers) -> int:
    up = client.post(
        "/api/v1/reports/upload",
        files={"file": ("cbc.pdf", _pdf("Hemoglobin 9.1 g/dL"), "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201, up.text
    return up.json()["report_id"]


def _analyzed(client, headers) -> int:
    rid = _upload(client, headers)
    assert client.post("/api/v1/reports/analyze", json={"report_id": rid}, headers=headers).status_code == 202
    assert client.get(f"/api/v1/reports/{rid}", headers=headers).json()["status"] == "analyzed"
    return rid


def test_export_streams_a_pdf(client):
    headers = _auth(client)
    rid = _analyzed(client, headers)
    resp = client.post("/api/v1/export", json={"report_id": rid}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 1000  # a real document, not an empty shell


def test_export_with_chat_included(client):
    headers = _auth(client)
    rid = _analyzed(client, headers)
    # Seed a report-scoped chat turn, then include it.
    client.post(
        "/api/v1/chat",
        json={"message": "What does hemoglobin measure?", "report_id": rid},
        headers=headers,
    )
    resp = client.post(
        "/api/v1/export", json={"report_id": rid, "include_chat": True}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_export_requires_analyzed_report(client):
    headers = _auth(client)
    rid = _upload(client, headers)  # uploaded, never analyzed
    assert client.post("/api/v1/export", json={"report_id": rid}, headers=headers).status_code == 409


def test_export_owner_scoped(client):
    owner = _auth(client)
    other = _auth(client)
    rid = _analyzed(client, owner)
    assert client.post("/api/v1/export", json={"report_id": rid}, headers=other).status_code == 404


def test_export_unknown_report_is_404(client):
    headers = _auth(client)
    assert client.post("/api/v1/export", json={"report_id": 999999}, headers=headers).status_code == 404


def test_export_requires_auth(client):
    assert client.post("/api/v1/export", json={"report_id": 1}).status_code == 401
