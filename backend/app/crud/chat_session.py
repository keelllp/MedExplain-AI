"""Chat-session data access (owner-scoped reads; newest-activity-first listing)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatSession, utcnow_iso


def create(db: Session, *, user_id: int, report_id: int | None, title: str) -> ChatSession:
    session = ChatSession(user_id=user_id, report_id=report_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_for_user(db: Session, session_id: int, user_id: int) -> ChatSession | None:
    """Owner-scoped lookup; returns None for missing OR not-owned (caller raises 404)."""
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def list_for_user(
    db: Session, user_id: int, limit: int, offset: int, report_id: int | None = None
) -> tuple[list[ChatSession], int]:
    filters = [ChatSession.user_id == user_id]
    if report_id is not None:
        filters.append(ChatSession.report_id == report_id)

    total = db.execute(
        select(func.count()).select_from(ChatSession).where(*filters)
    ).scalar_one()
    items = (
        db.execute(
            select(ChatSession)
            .where(*filters)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(items), total


def touch(db: Session, session: ChatSession) -> None:
    """Bump updated_at so the session sorts to the top of the activity-ordered list."""
    session.updated_at = utcnow_iso()
    db.commit()
