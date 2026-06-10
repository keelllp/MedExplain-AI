"""Export endpoint (Phase 10): stream a report-summary PDF.

Owner-scoped (cross-owner → 404); the report must be analyzed (else 409). The PDF carries the
full disclaimer block on every page; raw chat is excluded by default and, when included, each
assistant turn is re-guarded before embedding (D-EXPORT-CHAT). See docs/04-api-spec.md §4.17.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.exceptions import ConflictError, NotFoundError
from app.crud import abnormal_finding as abnormal_finding_crud
from app.crud import biomarker as biomarker_crud
from app.crud import chat_message as chat_message_crud
from app.crud import chat_session as chat_session_crud
from app.crud import doctor_question as doctor_question_crud
from app.crud import report as report_crud
from app.crud import summary as summary_crud
from app.models import User
from app.schemas.export import ExportRequest
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


def _filename(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (title or "report").strip()).strip("_")
    return (cleaned[:80] or "report") + ".pdf"


@router.post("")
def export_report(
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    report = report_crud.get_for_user(db, body.report_id, current_user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    if report.status != "analyzed":
        raise ConflictError("Report is not analyzed yet.")

    biomarkers = biomarker_crud.list_for_report(db, report.id)
    findings = abnormal_finding_crud.list_for_report(db, report.id)
    summary = summary_crud.get_latest_for_report(db, report.id)
    questions = doctor_question_crud.list_for_report(db, report.id)

    chat_turns = None
    if body.include_chat:
        chat_turns = []
        sessions, _ = chat_session_crud.list_for_user(
            db, current_user.id, limit=100, offset=0, report_id=report.id
        )
        for session in sessions:
            messages, _ = chat_message_crud.list_for_session(db, session.id, limit=1000, offset=0)
            chat_turns.extend(messages)

    pdf_bytes = export_service.build(report, biomarkers, findings, summary, questions, chat_turns)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(report.title)}"'},
    )
