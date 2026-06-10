"""Report-file data access."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReportFile


def create(
    db: Session, *, report_id: int, original_filename: str, stored_path: str,
    mime_type: str, size_bytes: int, page_count: int | None = None,
) -> ReportFile:
    report_file = ReportFile(
        report_id=report_id,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        size_bytes=size_bytes,
        page_count=page_count,
    )
    db.add(report_file)
    db.commit()
    db.refresh(report_file)
    return report_file


def get_primary(db: Session, report_id: int) -> ReportFile | None:
    return (
        db.execute(
            select(ReportFile).where(ReportFile.report_id == report_id).order_by(ReportFile.id.asc())
        )
        .scalars()
        .first()
    )


def list_for_report(db: Session, report_id: int) -> list[ReportFile]:
    return list(
        db.execute(
            select(ReportFile).where(ReportFile.report_id == report_id).order_by(ReportFile.id.asc())
        )
        .scalars()
        .all()
    )


def set_extraction(
    db: Session, report_file: ReportFile, *, raw_ocr_text: str,
    extracted_tables_json: str, page_count: int | None,
) -> None:
    report_file.raw_ocr_text = raw_ocr_text
    report_file.extracted_tables_json = extracted_tables_json
    if page_count is not None:
        report_file.page_count = page_count
    db.commit()
