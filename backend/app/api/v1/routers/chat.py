"""Chat endpoints (Phase 7): one RAG-grounded LLM call per message + session history.

All reads are owner-scoped (a cross-owner id returns 404, not 403, so existence is not
leaked — docs/04 §1). Generation reuses the Phase 5 safety guard + LLM router + KB via
``chat_service``; this router owns persistence (sessions + turns) and serializes the LLM
call behind the single analysis slot so chat never runs heavy inference concurrently with
a report analysis. See docs/04-api-spec.md §4.12–§4.15 and docs/08-rag-design.md §6.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.concurrency import analysis_semaphore
from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import ConflictError, NotFoundError
from app.crud import abnormal_finding as abnormal_finding_crud
from app.crud import biomarker as biomarker_crud
from app.crud import chat_message as chat_message_crud
from app.crud import chat_session as chat_session_crud
from app.crud import report as report_crud
from app.models import User
from app.schemas.chat import ChatMessageOut, ChatRequest, ChatResponse, ChatSessionOut
from app.schemas.common import Page
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

_HISTORY_TURNS = 6


def _title_from(message: str) -> str:
    """A short, human title derived from the opening message (single line)."""
    cleaned = " ".join(message.split())
    return (cleaned[:57] + "…") if len(cleaned) > 60 else (cleaned or "New chat")


def _parse_citations(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []  # malformed JSON must never 500 a history fetch


def _message_out(message) -> ChatMessageOut:
    return ChatMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        citations=_parse_citations(message.citations_json),
        created_at=message.created_at,
    )


@router.post("", response_model=ChatResponse)
def post_chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    # Resolve the session (owner-scoped) and the RAG scope. An existing session's own
    # report_id wins over the body's, so a session can't be re-pointed at another report.
    session = None
    if body.session_id is not None:
        session = chat_session_crud.get_for_user(db, body.session_id, current_user.id)
        if session is None:
            raise NotFoundError("Chat session not found.")
    scope_report_id = session.report_id if session is not None else body.report_id

    biomarkers: list = []
    findings: list = []
    if scope_report_id is not None:
        report = report_crud.get_for_user(db, scope_report_id, current_user.id)
        if report is None:
            raise NotFoundError("Report not found.")
        if report.status != "analyzed":
            raise ConflictError("Report is not analyzed yet.")
        biomarkers = biomarker_crud.list_for_report(db, scope_report_id)
        findings = abnormal_finding_crud.list_for_report(db, scope_report_id)

    history = (
        chat_message_crud.recent_for_session(db, session.id, _HISTORY_TURNS)
        if session is not None
        else []
    )

    # Serialize heavy inference with analysis (single-worker, CPU-only). If the slot is busy
    # past the timeout, answer from the deterministic floor rather than running two models.
    acquired = analysis_semaphore.acquire(timeout=settings.analysis_acquire_timeout)
    try:
        result = chat_service.answer_question(
            message=body.message,
            report_id=scope_report_id,
            biomarkers=biomarkers,
            findings=findings,
            history=history,
            user=current_user,
            allow_llm=acquired,
        )
    finally:
        if acquired:
            analysis_semaphore.release()

    # Persist: create the session on first turn, then the user + assistant turns.
    if session is None:
        session = chat_session_crud.create(
            db,
            user_id=current_user.id,
            report_id=scope_report_id,
            title=_title_from(body.message),
        )
    chat_message_crud.create(db, session_id=session.id, role="user", content=body.message)
    citations_json = (
        json.dumps(result["citations"], ensure_ascii=False) if result["citations"] else None
    )
    assistant = chat_message_crud.create(
        db,
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        citations_json=citations_json,
    )
    chat_session_crud.touch(db, session)

    return ChatResponse(
        session_id=session.id,
        message_id=assistant.id,
        answer=result["answer"],
        citations=result["citations"],
        refused=result["refused"],
        generation_mode=result["generation_mode"],
    )


@router.get("/sessions", response_model=Page[ChatSessionOut])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_id: int | None = Query(None, gt=0),
) -> Page[ChatSessionOut]:
    items, total = chat_session_crud.list_for_user(
        db, current_user.id, limit, offset, report_id
    )
    return Page[ChatSessionOut](
        items=[ChatSessionOut.model_validate(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionOut:
    session = chat_session_crud.get_for_user(db, session_id, current_user.id)
    if session is None:
        raise NotFoundError("Chat session not found.")
    return ChatSessionOut.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=Page[ChatMessageOut])
def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ChatMessageOut]:
    session = chat_session_crud.get_for_user(db, session_id, current_user.id)
    if session is None:
        raise NotFoundError("Chat session not found.")
    items, total = chat_message_crud.list_for_session(db, session_id, limit, offset)
    return Page[ChatMessageOut](
        items=[_message_out(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )
