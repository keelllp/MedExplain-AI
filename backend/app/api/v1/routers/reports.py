"""Report endpoints: upload, analyze (background), list, detail, delete.

All reads are owner-scoped (a cross-owner id returns 404, not 403, so existence is
not leaked — see docs/04 §1). Upload validates by magic bytes (not the client
content-type), enforces exactly one file and the size cap, and stores files outside
the web root under data/uploads/{user_id}/ with a non-guessable name.
"""

from __future__ import annotations

import json
import os
import re
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.crud import abnormal_finding as abnormal_finding_crud
from app.crud import biomarker as biomarker_crud
from app.crud import doctor_question as doctor_question_crud
from app.crud import report as report_crud
from app.crud import report_file as report_file_crud
from app.crud import summary as summary_crud
from app.models import User
from app.schemas.biomarker import AbnormalFindingOut, BiomarkerOut
from app.schemas.common import Message, Page, ReportType
from app.schemas.doctor_question import DoctorQuestionOut
from app.schemas.summary import SummaryOut
from app.schemas.report import (
    AnalyzeAcceptedResponse,
    AnalyzeIn,
    ReportDetailOut,
    ReportSummaryOut,
    ReportUploadResponse,
)
from app.services import doc_service
from app.services.analysis_pipeline import run_analysis

logger = get_logger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


def _finding_out(finding) -> AbnormalFindingOut:
    citations: list = []
    if finding.citations_json:
        try:
            parsed = json.loads(finding.citations_json)
            if isinstance(parsed, list):
                citations = parsed
        except (ValueError, TypeError):
            citations = []  # malformed JSON must not 500 the detail endpoint
    return AbnormalFindingOut(
        id=finding.id,
        biomarker_id=finding.biomarker_id,
        status=finding.status,
        severity=finding.severity,
        direction=finding.direction,
        rule_id=finding.rule_id,
        explanation=finding.explanation,
        citations=citations,
    )


def _to_detail(report, biomarkers, findings, summary, doctor_questions) -> ReportDetailOut:
    return ReportDetailOut(
        id=report.id,
        title=report.title,
        report_type=report.report_type,
        status=report.status,
        progress=report.progress,
        error_code=report.error_code,
        ocr_confidence=report.ocr_confidence,
        uploaded_at=report.uploaded_at,
        analyzed_at=report.analyzed_at,
        biomarkers=[BiomarkerOut.model_validate(b) for b in biomarkers],
        findings=[_finding_out(f) for f in findings],
        summary=SummaryOut.model_validate(summary) if summary is not None else None,
        doctor_questions=[DoctorQuestionOut.model_validate(q) for q in doctor_questions],
    )


def _safe_filename(name: str | None) -> str:
    cleaned = re.sub(r"[\x00-\x1f]", "", (name or "").strip())
    return cleaned[:255] or "upload"


@router.post("/upload", response_model=ReportUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(
    request: Request,
    file: list[UploadFile] = File(...),
    title: str | None = Form(default=None),
    report_type: ReportType = Form(default=ReportType.other),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportUploadResponse:
    if len(file) != 1:  # exactly one file part (per D-SINGLEFILE)
        raise ValidationAppError("Upload exactly one file.")
    upload = file[0]

    max_bytes = settings.max_upload_bytes
    # Early reject via Content-Length (avoids spooling a huge body to a temp file).
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )

    content = await upload.read(max_bytes + 1)  # cap memory: read at most limit+1
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )
    if not content:
        raise ValidationAppError("Uploaded file is empty.")

    mime = doc_service.sniff_mime(content[:16])  # trust magic bytes, not the client
    if mime not in doc_service.ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a PDF, JPG, or PNG.",
        )

    user_dir = settings.upload_path / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_path = user_dir / f"{uuid.uuid4().hex}{doc_service.EXT_BY_MIME[mime]}"
    stored_path.write_bytes(content)

    original_filename = _safe_filename(upload.filename or stored_path.name)
    resolved_title = (
        (title or upload.filename or "Untitled report").strip()[:200] or "Untitled report"
    )
    try:
        report = report_crud.create(
            db, user_id=current_user.id, title=resolved_title, report_type=report_type.value
        )
        report_file = report_file_crud.create(
            db,
            report_id=report.id,
            original_filename=original_filename,
            stored_path=str(stored_path),
            mime_type=mime,
            size_bytes=len(content),
        )
    except Exception:
        # Don't leak an untracked file on disk if the DB write fails.
        try:
            os.remove(stored_path)
        except OSError:
            pass
        raise

    return ReportUploadResponse(
        report_id=report.id,
        status=report.status,
        original_filename=report_file.original_filename,
        mime_type=mime,
        size_bytes=len(content),
    )


@router.post("/analyze", response_model=AnalyzeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def analyze_report(
    body: AnalyzeIn,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyzeAcceptedResponse:
    report = report_crud.get_for_user(db, body.report_id, current_user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    if report.status == "processing":
        raise ConflictError("Analysis already in progress.")

    # Re-analyzing an uploaded/failed/analyzed report resets progress + clears error_code.
    report_crud.set_status(db, report, status="processing", progress=0, error_code=None)
    background.add_task(run_analysis, report.id)
    return AnalyzeAcceptedResponse(report_id=report.id, status=report.status, progress=report.progress)


@router.get("", response_model=Page[ReportSummaryOut])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ReportSummaryOut]:
    items, total = report_crud.list_for_user(db, current_user.id, limit, offset)
    return Page[ReportSummaryOut](
        items=[ReportSummaryOut.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=ReportDetailOut)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    report = report_crud.get_for_user(db, report_id, current_user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    biomarkers = biomarker_crud.list_for_report(db, report_id)
    findings = abnormal_finding_crud.list_for_report(db, report_id)
    summary = summary_crud.get_latest_for_report(db, report_id)
    doctor_questions = doctor_question_crud.list_for_report(db, report_id)
    return _to_detail(report, biomarkers, findings, summary, doctor_questions)


@router.delete("/{report_id}", response_model=Message)
def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    report = report_crud.get_for_user(db, report_id, current_user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    if report.status == "processing":
        raise ConflictError("Cannot delete a report while it is being analyzed.")

    # Capture paths BEFORE delete: commit expires the ORM objects and the rows are
    # cascade-deleted, so reading attributes afterward raises ObjectDeletedError.
    stored_paths = [f.stored_path for f in report_file_crud.list_for_report(db, report_id)]
    report_crud.delete(db, report)  # DB cascade removes file rows
    for path in stored_paths:
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning("Could not remove file for deleted report %s: %s", report_id, exc)
    return Message(message="Report deleted.")
