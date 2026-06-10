"""Correctness-critical lifecycle tests: startup reconciler, FK cascade, token edges."""

import datetime as dt

import jwt
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.crud import user as user_crud
from app.db.reconcile import reconcile_stuck_reports
from app.models import Report, User

pytestmark = pytest.mark.integration


def _make_user(db, email: str) -> User:
    return user_crud.create_user(db, email=email, password="password123", full_name="X")


def test_reconciler_marks_stuck_processing_as_failed(db_session):
    db = db_session
    user = _make_user(db, "reconcile@example.com")
    report = Report(user_id=user.id, title="stuck", status="processing", progress=40)
    db.add(report)
    db.commit()
    report_id = report.id

    count = reconcile_stuck_reports(db)
    assert count >= 1

    db.expire_all()
    refreshed = db.get(Report, report_id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "timeout"  # enumerated, no raw error text


def test_foreign_keys_enforced_and_delete_cascades(db_session):
    db = db_session
    # The PRAGMA must be ON on this connection or ON DELETE CASCADE won't fire.
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1

    user = _make_user(db, "cascade@example.com")
    report = Report(user_id=user.id, title="child report")
    db.add(report)
    db.commit()
    report_id, user_id = report.id, user.id
    assert db.get(Report, report_id) is not None

    user_crud.delete_user(db, user)
    db.expire_all()

    # Deleting the user cascades to the child report (DB-level ON DELETE CASCADE).
    assert db.get(User, user_id) is None
    assert db.get(Report, report_id) is None


def _signed(payload: dict) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_non_access_token_rejected(client):
    exp = int((dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).timestamp())
    token = _signed({"sub": "1", "type": "refresh", "exp": exp})  # valid signature, wrong type
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_expired_access_token_rejected(client):
    past = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).timestamp())
    token = _signed({"sub": "1", "type": "access", "iat": past - 60, "exp": past})
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_garbage_token_rejected(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
