"""Integration tests for the chat surface (Phase 7).

Offline by design: conftest points the LLM at a dead Ollama port and clears the Gemini
key, so every answer comes from the deterministic floor + guarded — no network, no model
download. Retrieval (and therefore citations) is the deterministic canonical-name KB path,
so these assertions are stable without an LLM.
"""

import uuid

import pymupdf
import pytest

from app.schemas.common import DISCLAIMER

pytestmark = pytest.mark.integration


def _auth_headers(client) -> dict:
    email = f"c-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _analyzed_report(client, headers, text="Hemoglobin 9.1 g/dL   Glucose 88 mg/dL") -> int:
    """Upload + analyze a native-text PDF (TestClient runs analysis synchronously)."""
    up = client.post(
        "/api/v1/reports/upload",
        files={"file": ("cbc.pdf", _pdf_bytes(text), "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201, up.text
    report_id = up.json()["report_id"]
    an = client.post("/api/v1/reports/analyze", json={"report_id": report_id}, headers=headers)
    assert an.status_code == 202, an.text
    detail = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert detail["status"] == "analyzed", detail
    return report_id


def _post_chat(client, headers, **body) -> dict:
    resp = client.post("/api/v1/chat", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Core behavior
# --------------------------------------------------------------------------- #
def test_general_chat_creates_session_and_carries_disclaimer(client):
    headers = _auth_headers(client)
    data = _post_chat(client, headers, message="What does hemoglobin measure?")

    assert data["session_id"] > 0
    assert data["message_id"] > 0
    assert data["refused"] is False
    assert data["generation_mode"] == "offline_template"  # Ollama dead in tests
    assert DISCLAIMER in data["answer"]
    assert data["disclaimer"] == DISCLAIMER
    # The marker was named → deterministic KB retrieval attaches a citation in chat shape.
    assert data["citations"], "expected a KB citation for a named marker"
    cite = data["citations"][0]
    assert set(cite) == {"doc", "chunk_id", "score"}
    assert cite["doc"] == "Hemoglobin"
    assert cite["chunk_id"].startswith("hemoglobin#")


def test_session_is_reused_and_history_is_chronological(client):
    headers = _auth_headers(client)
    first = _post_chat(client, headers, message="What does hemoglobin measure?")
    sid = first["session_id"]
    second = _post_chat(client, headers, message="And what about glucose?", session_id=sid)
    assert second["session_id"] == sid  # same session, not a new one

    msgs = client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=headers).json()
    assert msgs["total"] == 4
    roles = [m["role"] for m in msgs["items"]]
    assert roles == ["user", "assistant", "user", "assistant"]  # oldest-first
    # Assistant turns are guarded; user turns are verbatim.
    assistant_turns = [m for m in msgs["items"] if m["role"] == "assistant"]
    assert all(DISCLAIMER in m["content"] for m in assistant_turns)


def test_report_scoped_chat_cites_report_marker(client):
    headers = _auth_headers(client)
    report_id = _analyzed_report(client, headers)
    data = _post_chat(client, headers, message="Can you explain my hemoglobin?", report_id=report_id)

    assert data["citations"], "report-scoped chat should cite the report's marker"
    assert any(c["doc"] == "Hemoglobin" for c in data["citations"])
    assert DISCLAIMER in data["answer"]

    session = client.get(
        f"/api/v1/chat/sessions/{data['session_id']}", headers=headers
    ).json()
    assert session["report_id"] == report_id


def test_diagnosis_request_is_refused(client):
    headers = _auth_headers(client)
    data = _post_chat(client, headers, message="What disease do I have based on this?")
    assert data["refused"] is True
    assert data["citations"] == []
    assert DISCLAIMER in data["answer"]
    assert "not a doctor" in data["answer"].lower()


def test_report_scoped_chat_requires_analyzed_report(client):
    headers = _auth_headers(client)
    up = client.post(
        "/api/v1/reports/upload",
        files={"file": ("cbc.pdf", _pdf_bytes("Hemoglobin 9.1 g/dL"), "application/pdf")},
        headers=headers,
    )
    report_id = up.json()["report_id"]  # uploaded, never analyzed
    resp = client.post(
        "/api/v1/chat", json={"message": "Explain this", "report_id": report_id}, headers=headers
    )
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# Sessions API
# --------------------------------------------------------------------------- #
def test_list_sessions_newest_first_and_report_filter(client):
    headers = _auth_headers(client)
    report_id = _analyzed_report(client, headers)
    general = _post_chat(client, headers, message="What does glucose measure?")["session_id"]
    scoped = _post_chat(client, headers, message="Explain my hemoglobin", report_id=report_id)[
        "session_id"
    ]

    listing = client.get("/api/v1/chat/sessions", headers=headers).json()
    assert listing["total"] == 2
    assert listing["items"][0]["id"] == scoped  # most-recent activity first

    filtered = client.get(
        f"/api/v1/chat/sessions?report_id={report_id}", headers=headers
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == scoped
    assert filtered["items"][0]["report_id"] == report_id
    assert general not in [s["id"] for s in filtered["items"]]


# --------------------------------------------------------------------------- #
# Auth + owner-scoping + validation
# --------------------------------------------------------------------------- #
def test_chat_requires_auth(client):
    assert client.post("/api/v1/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/api/v1/chat/sessions").status_code == 401


def test_owner_scoping(client):
    owner = _auth_headers(client)
    other = _auth_headers(client)
    report_id = _analyzed_report(client, owner)
    sid = _post_chat(client, owner, message="What does hemoglobin measure?")["session_id"]

    # Another user can neither see nor post into the owner's session, nor scope to the report.
    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=other).status_code == 404
    assert client.get(f"/api/v1/chat/sessions/{sid}/messages", headers=other).status_code == 404
    assert client.post(
        "/api/v1/chat", json={"message": "hi", "session_id": sid}, headers=other
    ).status_code == 404
    assert client.post(
        "/api/v1/chat", json={"message": "hi", "report_id": report_id}, headers=other
    ).status_code == 404
    # Owner still has access.
    assert client.get(f"/api/v1/chat/sessions/{sid}", headers=owner).status_code == 200


def test_unknown_session_is_404(client):
    headers = _auth_headers(client)
    assert client.post(
        "/api/v1/chat", json={"message": "hi", "session_id": 999999}, headers=headers
    ).status_code == 404
    assert client.get("/api/v1/chat/sessions/999999", headers=headers).status_code == 404


@pytest.mark.parametrize("message", ["", "a" * 4001])
def test_message_validation(client, message):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/chat", json={"message": message}, headers=headers)
    assert resp.status_code == 422
