"""Chat-message data access (chronological history per session)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage


def create(
    db: Session, *, session_id: int, role: str, content: str, citations_json: str | None = None
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id, role=role, content=content, citations_json=citations_json
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_for_session(
    db: Session, session_id: int, limit: int, offset: int
) -> tuple[list[ChatMessage], int]:
    """Oldest-first (chronological for rendering)."""
    total = db.execute(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    ).scalar_one()
    items = (
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(items), total


def recent_for_session(db: Session, session_id: int, limit: int) -> list[ChatMessage]:
    """The last ``limit`` messages, returned in chronological order (for prompt context)."""
    rows = (
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(reversed(rows))
