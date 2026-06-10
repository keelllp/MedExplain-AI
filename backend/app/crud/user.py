"""User data access. Email is stored/looked-up normalized (lowercased)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import User, utcnow_iso


def _norm(email: str) -> str:
    return email.strip().lower()


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == _norm(email))).scalar_one_or_none()


def create_user(db: Session, *, email: str, password: str, full_name: str | None = None) -> User:
    # New accounts inherit the configured default generation policy. When that default is
    # 'cloud' we also grant + stamp Gemini egress consent so the LLM router actually uses
    # it (resolve_provider requires consent). With no server key, 'cloud' degrades to the
    # offline template anyway, so this never causes silent egress without a key present.
    mode = settings.default_llm_mode if settings.default_llm_mode in ("cloud", "offline") else "offline"
    user = User(
        email=_norm(email),
        password_hash=hash_password(password),
        full_name=full_name,
        llm_mode=mode,
        gemini_consent=1 if mode == "cloud" else 0,
        gemini_consented_at=utcnow_iso() if mode == "cloud" else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def update_profile(db: Session, user: User, updates: dict) -> User:
    # Only assign keys that were explicitly provided (partial PATCH update).
    if "full_name" in updates:
        user.full_name = updates["full_name"]
    user.updated_at = utcnow_iso()
    db.commit()
    db.refresh(user)
    return user


def set_llm_mode(db: Session, user: User, *, llm_mode: str) -> User:
    user.llm_mode = llm_mode
    # Recording (re-affirming) consent every time cloud is enabled avoids stale consent.
    if llm_mode == "cloud":
        user.gemini_consent = 1
        user.gemini_consented_at = utcnow_iso()
    user.updated_at = utcnow_iso()
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow_iso()
    db.commit()


def delete_user(db: Session, user: User) -> None:
    # Child rows (reports, chat_sessions, ...) are removed by DB ON DELETE CASCADE
    # (PRAGMA foreign_keys=ON). File/vector cleanup is wired in P3/P5.
    db.delete(user)
    db.commit()
