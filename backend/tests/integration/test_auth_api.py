"""Integration tests for the auth + account API surface (DoD for Phase 2).

Contract per docs/04-api-spec.md: register returns UserOut (201); a token is
obtained via /auth/login.
"""

import uuid

import pytest

pytestmark = pytest.mark.integration


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email: str, password: str = "password123", full_name: str | None = None):
    payload = {"email": email, "password": password}
    if full_name is not None:
        payload["full_name"] = full_name
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _login_token(client, email: str, password: str = "password123") -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_lists_all_endpoints(client):
    spec = client.get("/api/v1/openapi.json").json()
    paths = set(spec["paths"])
    expected = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/users/me",
        "/api/v1/users/me/settings",
        "/api/v1/reports/upload",
        "/api/v1/reports/analyze",
        "/api/v1/reports",
        "/api/v1/reports/{report_id}",
        "/api/v1/chat",
        "/api/v1/trends",
        "/api/v1/export",
    }
    missing = expected - paths
    assert not missing, f"missing endpoints in OpenAPI: {missing}"


def test_register_returns_userout_then_login(client):
    email = _unique_email()

    user = _register(client, email, full_name="Test User")
    # register returns UserOut (NOT a token)
    assert "access_token" not in user
    assert user["email"] == email
    assert user["full_name"] == "Test User"
    assert user["llm_mode"] == "offline"  # privacy-first default
    assert user["gemini_consent"] is False
    assert "created_at" in user and "updated_at" in user  # full UserOut contract

    # duplicate email -> 409
    dup = client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"

    # case-insensitive duplicate is also rejected (DB COLLATE NOCASE + app normalization)
    dup2 = client.post(
        "/api/v1/auth/register", json={"email": email.upper(), "password": "password123"}
    )
    assert dup2.status_code == 409

    # login issues a bearer token
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    token = body["access_token"]

    # wrong password -> 401
    bad = client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "unauthorized"

    # /me requires auth
    assert client.get("/api/v1/auth/me").status_code == 401

    # /me with token
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_cloud_default_grants_consent_for_new_accounts(client, monkeypatch):
    # When the deployment defaults new accounts to Gemini, registration records cloud mode
    # + stamped consent (the suite otherwise pins this to 'offline'; see conftest).
    from app.crud import user as user_crud

    monkeypatch.setattr(user_crud.settings, "default_llm_mode", "cloud")
    user = _register(client, _unique_email())
    assert user["llm_mode"] == "cloud"
    assert user["gemini_consent"] is True
    assert user["gemini_consented_at"] is not None


def test_short_password_rejected_with_field_details(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "short"},
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    # details is a list of {field, issue} per docs/04 §1.3
    assert isinstance(err["details"], list) and err["details"]
    assert {"field", "issue"} <= set(err["details"][0])
    assert any(d["field"] == "password" for d in err["details"])


def test_patch_me_partial_does_not_wipe_name(client):
    email = _unique_email()
    _register(client, email, full_name="Keep Me")
    headers = {"Authorization": f"Bearer {_login_token(client, email)}"}

    # empty PATCH body must NOT null out full_name
    resp = client.patch("/api/v1/users/me", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Keep Me"

    # explicit update works
    resp2 = client.patch("/api/v1/users/me", json={"full_name": "Renamed"}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["full_name"] == "Renamed"


def test_settings_password_and_delete(client):
    email = _unique_email()
    _register(client, email)
    headers = {"Authorization": f"Bearer {_login_token(client, email)}"}

    # cloud mode requires a configured Gemini key (none in tests) -> 403 forbidden
    cloud = client.patch("/api/v1/users/me/settings", json={"llm_mode": "cloud"}, headers=headers)
    assert cloud.status_code == 403
    assert cloud.json()["error"]["code"] == "forbidden"

    # offline mode is fine
    offline = client.patch(
        "/api/v1/users/me/settings", json={"llm_mode": "offline"}, headers=headers
    )
    assert offline.status_code == 200
    assert offline.json()["llm_mode"] == "offline"

    # change password: new must differ from current
    same = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "password123", "new_password": "password123"},
        headers=headers,
    )
    assert same.status_code == 422

    chg = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"},
        headers=headers,
    )
    assert chg.status_code == 200
    assert _login_token(client, email, "newpassword123")  # new password works

    # delete account -> the same token is then unauthorized (user is gone)
    assert client.delete("/api/v1/users/me", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


# (All v1 endpoints are implemented as of Phase 10 — no 501 stubs remain. Each surface has
# its own auth + behavior tests: see test_reports_api / test_chat_api / test_trends_api /
# test_export_api.)
