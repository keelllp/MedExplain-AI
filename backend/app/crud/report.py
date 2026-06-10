"""Report data access (owner-scoped reads; status/progress transitions)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Report, utcnow_iso

_UNSET = object()


def create(db: Session, *, user_id: int, title: str, report_type: str) -> Report:
    report = Report(user_id=user_id, title=title, report_type=report_type)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get(db: Session, report_id: int) -> Report | None:
    """Internal lookup (NO owner check) — for the background pipeline."""
    return db.get(Report, report_id)


def get_for_user(db: Session, report_id: int, user_id: int) -> Report | None:
    """Owner-scoped lookup; returns None for missing OR not-owned (caller raises 404)."""
    report = db.get(Report, report_id)
    if report is None or report.user_id != user_id:
        return None
    return report


def list_for_user(
    db: Session, user_id: int, limit: int, offset: int
) -> tuple[list[Report], int]:
    total = db.execute(
        select(func.count()).select_from(Report).where(Report.user_id == user_id)
    ).scalar_one()
    items = (
        db.execute(
            select(Report)
            .where(Report.user_id == user_id)
            .order_by(Report.uploaded_at.desc(), Report.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(items), total


def set_status(
    db: Session, report: Report, *, status: str | None = None,
    progress: int | None = None, error_code=_UNSET,
) -> Report:
    if status is not None:
        report.status = status
    if progress is not None:
        report.progress = progress
    if error_code is not _UNSET:
        report.error_code = error_code
    report.updated_at = utcnow_iso()
    db.commit()
    db.refresh(report)
    return report


def set_ocr_confidence(db: Session, report: Report, value: float | None) -> None:
    report.ocr_confidence = value
    report.updated_at = utcnow_iso()
    db.commit()


def finalize_analyzed(db: Session, report: Report) -> None:
    report.status = "analyzed"
    report.progress = 100
    report.error_code = None
    report.analyzed_at = utcnow_iso()
    report.updated_at = utcnow_iso()
    db.commit()


def mark_failed(db: Session, report_id: int, error_code: str) -> None:
    report = db.get(Report, report_id)
    if report is None:
        return
    report.status = "failed"
    report.error_code = error_code
    report.progress = 0  # progress is meaningless once failed
    report.updated_at = utcnow_iso()
    db.commit()


def delete(db: Session, report: Report) -> None:
    # report_files rows cascade via DB FK; on-disk files are removed by the caller.
    db.delete(report)
    db.commit()
