"""Integration tests for the report upload/analyze/list/get/delete surface.

The native-PDF path is exercised end to end (TestClient runs the analyze
BackgroundTask synchronously). The OCR/image path is validated separately by a smoke
script to keep this suite fast and offline (no model download).
"""

import os
import uuid

import pymupdf
import pytest
from PIL import Image

from app.crud import report_file as report_file_crud
from app.schemas.common import DISCLAIMER

pytestmark = pytest.mark.integration


def _auth_headers(client) -> dict:
    email = f"r-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _text_pdf_bytes(text="Hemoglobin 13.5 g/dL   WBC 7.2 10^3/uL") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _png_bytes() -> bytes:
    import io

    buf = io.BytesIO()
    Image.new("RGB", (24, 24), "white").save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, headers, **form) -> dict:
    resp = client.post(
        "/api/v1/reports/upload",
        files={"file": ("cbc.pdf", _text_pdf_bytes(), "application/pdf")},
        data=form or None,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/v1/reports/upload",
        files={"file": ("a.pdf", _text_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 401


def test_upload_response_shape(client):
    headers = _auth_headers(client)
    body = _upload(client, headers)
    # ReportUploadResponse is flat (docs/04 §4.8): report_id + file metadata, no token/files.
    assert set(body) >= {"report_id", "status", "original_filename", "mime_type", "size_bytes"}
    assert body["status"] == "uploaded"
    assert body["mime_type"] == "application/pdf"
    assert body["original_filename"] == "cbc.pdf"
    assert "files" not in body


def test_upload_rejects_unsupported_type(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/v1/reports/upload",
        files={"file": ("a.txt", b"just plain text, not a real document", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 415


def test_upload_rejects_oversize(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 0)
    headers = _auth_headers(client)
    resp = client.post(
        "/api/v1/reports/upload",
        files={"file": ("a.pdf", _text_pdf_bytes(), "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 413


def test_multiple_files_rejected(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/v1/reports/upload",
        files=[
            ("file", ("a.pdf", _text_pdf_bytes(), "application/pdf")),
            ("file", ("b.pdf", _text_pdf_bytes(), "application/pdf")),
        ],
        headers=headers,
    )
    assert resp.status_code == 422


def test_upload_then_analyze_native_pdf(client, db_session):
    headers = _auth_headers(client)
    body = _upload(client, headers, title="April CBC", report_type="cbc")
    report_id = body["report_id"]

    # Detail carries title/report_type (+ the disclaimer + empty P4/P5 arrays).
    pre = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert pre["title"] == "April CBC"
    assert pre["report_type"] == "cbc"
    assert pre["status"] == "uploaded"
    assert pre["biomarkers"] == [] and pre["findings"] == [] and pre["doctor_questions"] == []
    assert pre["summary"] is None
    assert pre["disclaimer"]

    analyze = client.post("/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers)
    assert analyze.status_code == 202
    assert analyze.json()["report_id"] == report_id  # frozen contract uses report_id

    # TestClient runs the BackgroundTask synchronously, so analysis is already done.
    detail = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert detail["status"] == "analyzed"
    assert detail["progress"] == 100
    assert detail["ocr_confidence"] == 1.0  # native text → high confidence (no OCR)

    # page_count + native text are persisted (not exposed via the detail API → check DB).
    report_file = report_file_crud.get_primary(db_session, report_id)
    db_session.refresh(report_file)
    assert report_file.page_count == 1
    assert "Hemoglobin" in (report_file.raw_ocr_text or "")


def test_double_analyze_conflicts_when_processing(client, monkeypatch):
    import app.api.v1.routers.reports as reports_router

    monkeypatch.setattr(reports_router, "run_analysis", lambda report_id: None)
    headers = _auth_headers(client)
    report_id = _upload(client, headers)["report_id"]

    assert client.post(
        "/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers
    ).status_code == 202
    assert client.post(
        "/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers
    ).status_code == 409


def test_cannot_delete_while_processing(client, monkeypatch):
    import app.api.v1.routers.reports as reports_router

    monkeypatch.setattr(reports_router, "run_analysis", lambda report_id: None)
    headers = _auth_headers(client)
    report_id = _upload(client, headers)["report_id"]
    client.post("/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers)
    assert client.delete(f"/api/v1/reports/{report_id}", headers=headers).status_code == 409


def test_owner_scoping(client):
    owner = _auth_headers(client)
    other = _auth_headers(client)
    report_id = _upload(client, owner)["report_id"]

    assert client.get(f"/api/v1/reports/{report_id}", headers=other).status_code == 404
    assert (
        client.post(
            "/api/v1/reports/analyze", json={"report_id": report_id}, headers=other
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/reports/{report_id}", headers=other).status_code == 404
    assert client.get(f"/api/v1/reports/{report_id}", headers=owner).status_code == 200


def test_list_and_delete_removes_file(client, db_session):
    headers = _auth_headers(client)
    report_id = _upload(client, headers)["report_id"]

    listing = client.get("/api/v1/reports", headers=headers).json()
    assert listing["total"] >= 1
    assert any(item["id"] == report_id for item in listing["items"])

    stored_path = report_file_crud.get_primary(db_session, report_id).stored_path
    assert os.path.exists(stored_path)

    assert client.delete(f"/api/v1/reports/{report_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/reports/{report_id}", headers=headers).status_code == 404
    assert not os.path.exists(stored_path)


def test_image_upload_accepted(client):
    headers = _auth_headers(client)
    resp = client.post(
        "/api/v1/reports/upload",
        files={"file": ("scan.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["mime_type"] == "image/png"


def _report_pdf_bytes(lines) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 24
    data = doc.tobytes()
    doc.close()
    return data


def test_analyze_extracts_biomarkers_and_findings(client):
    headers = _auth_headers(client)
    pdf = _report_pdf_bytes(
        ["Hemoglobin 9.1 g/dL 13.0-17.0", "WBC 7.2 10^3/uL 4.0-11.0", "Glucose 180 mg/dL 70-99"]
    )
    report_id = client.post(
        "/api/v1/reports/upload",
        files={"file": ("labs.pdf", pdf, "application/pdf")},
        headers=headers,
    ).json()["report_id"]
    assert client.post(
        "/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers
    ).status_code == 202

    detail = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert detail["status"] == "analyzed"

    by_name = {b["canonical_name"]: b for b in detail["biomarkers"]}
    assert by_name["hemoglobin"]["value"] == 9.1
    assert "wbc" in by_name and "glucose" in by_name

    findings = {f["biomarker_id"]: f for f in detail["findings"]}
    hb = findings[by_name["hemoglobin"]["id"]]
    assert hb["status"] == "abnormal" and hb["direction"] == "low"
    glu = findings[by_name["glucose"]["id"]]
    assert glu["status"] == "abnormal" and glu["direction"] == "high"

    # Phase 5: guarded explanations + overall summary + doctor questions are now present.
    assert hb["explanation"] and DISCLAIMER in hb["explanation"]
    assert hb["citations"] and hb["citations"][0]["doc_title"] == "Hemoglobin"
    assert detail["summary"] is not None
    assert DISCLAIMER in detail["summary"]["summary_text"]
    assert detail["summary"]["generation_mode"] == "offline_template"  # no LLM in tests
    assert len(detail["doctor_questions"]) >= 1
    assert detail["disclaimer"]


def test_reanalyze_is_idempotent(client):
    headers = _auth_headers(client)
    pdf = _report_pdf_bytes(["Hemoglobin 9.1 g/dL 13.0-17.0", "Glucose 180 mg/dL 70-99"])
    report_id = client.post(
        "/api/v1/reports/upload",
        files={"file": ("a.pdf", pdf, "application/pdf")},
        headers=headers,
    ).json()["report_id"]

    client.post("/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers)
    first = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert len(first["biomarkers"]) >= 2  # sanity: extraction worked

    client.post("/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers)
    second = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()

    # re-analyze must not duplicate biomarkers/findings
    assert len(second["biomarkers"]) == len(first["biomarkers"])
    assert len(second["findings"]) == len(first["findings"])
