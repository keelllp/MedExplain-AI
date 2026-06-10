"""Analysis pipeline orchestration (background job).

Phase 3 implements the document stage only: native-text extraction (+ OCR for image
pages) → persist raw text/tables/confidence → progress 25 → finalize. Phases 4–5 will
insert extraction (50) → rules (70) → explanations (100) before the finalize step.

Runs in Starlette's threadpool via BackgroundTasks; serialized by the analysis
semaphore (acquired with a timeout so a queued job can't occupy a threadpool slot
forever); uses its own DB session. Never raises — failures persist as enumerated codes.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.concurrency import analysis_semaphore
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.crud import abnormal_finding as abnormal_finding_crud
from app.crud import biomarker as biomarker_crud
from app.crud import doctor_question as doctor_question_crud
from app.crud import report as report_crud
from app.crud import report_file as report_file_crud
from app.crud import summary as summary_crud
from app.crud import user as user_crud
from app.services import (
    abnormality_service,
    doc_service,
    explanation_service,
    extraction_service,
    ocr_service,
)

logger = get_logger(__name__)


def run_analysis(report_id: int) -> None:
    acquired = analysis_semaphore.acquire(timeout=settings.analysis_acquire_timeout)
    if not acquired:
        logger.warning("Timed out waiting for the analysis slot (report %s)", report_id)
        _fail_fresh(report_id, "timeout")
        return
    try:
        db = SessionLocal()
        try:
            _run(db, report_id)
        except doc_service.ExtractionError:
            logger.warning("Extraction rejected report %s", report_id)
            _safe_fail(db, report_id, "extraction_failed")
        except ocr_service.OcrUnavailableError:
            logger.warning("OCR unavailable for report %s", report_id)
            _safe_fail(db, report_id, "ocr_failed")
        except FileNotFoundError:
            logger.warning("Stored file missing for report %s", report_id)
            _safe_fail(db, report_id, "internal_error")
        except Exception:  # noqa: BLE001 - last-resort guard; details logged, never stored
            logger.exception("Analysis failed for report %s", report_id)
            _safe_fail(db, report_id, "internal_error")
        finally:
            db.close()
    finally:
        analysis_semaphore.release()


def _safe_fail(db: Session, report_id: int, code: str) -> None:
    # Clear any poisoned transaction before the failure write (avoids PendingRollbackError).
    try:
        db.rollback()
    except Exception:  # noqa: BLE001
        pass
    report_crud.mark_failed(db, report_id, error_code=code)


def _fail_fresh(report_id: int, code: str) -> None:
    db = SessionLocal()
    try:
        report_crud.mark_failed(db, report_id, error_code=code)
    finally:
        db.close()


def _run(db: Session, report_id: int) -> None:
    report = report_crud.get(db, report_id)
    if report is None:
        logger.warning("Analyze: report %s no longer exists", report_id)
        return
    report_file = report_file_crud.get_primary(db, report_id)
    if report_file is None:
        _safe_fail(db, report_id, "internal_error")
        return

    report_crud.set_status(db, report, status="processing", progress=0, error_code=None)

    extraction = doc_service.load(report_file.stored_path, report_file.mime_type)

    ocr_confidences: list[float] = []
    ocr_unavailable = False
    for page in extraction.pages:
        if not page.needs_ocr:
            continue
        png = doc_service.page_image_png(
            report_file.stored_path, report_file.mime_type, page.index
        )
        try:
            text, confidence = ocr_service.ocr_image_png(png)
        except ocr_service.OcrUnavailableError:
            ocr_unavailable = True
            break
        page.text = text
        ocr_confidences.append(confidence)

    raw_text = "\n\n".join(p.text for p in extraction.pages if p.text).strip()

    # OCR needed but unavailable: fail only if we recovered NO text at all; otherwise
    # keep the native text we did extract (partial result) rather than losing everything.
    if ocr_unavailable and not raw_text:
        raise ocr_service.OcrUnavailableError("OCR required but unavailable")

    tables_json = json.dumps(extraction.tables, ensure_ascii=False)
    if ocr_confidences:
        ocr_confidence = sum(ocr_confidences) / len(ocr_confidences)
    else:
        ocr_confidence = 1.0 if raw_text else None  # native text layer = high confidence

    report_file_crud.set_extraction(
        db,
        report_file,
        raw_ocr_text=raw_text,
        extracted_tables_json=tables_json,
        page_count=extraction.page_count,
    )
    report_crud.set_status(db, report, progress=25)  # document stage complete
    report_crud.set_ocr_confidence(db, report, ocr_confidence)

    # Stage 2 — extraction + normalization (catalog-anchored, deterministic).
    # Delete any prior rows first so re-analysis is idempotent (findings cascade via FK;
    # summaries + doctor_questions are report-scoped, so delete them explicitly).
    biomarker_crud.delete_for_report(db, report.id)
    summary_crud.delete_for_report(db, report.id)
    doctor_question_crud.delete_for_report(db, report.id)
    raw_biomarkers = extraction_service.extract(raw_text, extraction.tables)
    biomarker_crud.bulk_insert(db, report.id, raw_biomarkers)
    report_crud.set_status(db, report, progress=50)

    # Stage 3 — deterministic abnormality rules (no LLM, no user-facing prose yet).
    biomarkers = biomarker_crud.list_for_report(db, report.id)
    finding_rows = [
        {"biomarker_id": bm.id, **verdict}
        for bm in biomarkers
        if (verdict := abnormality_service.evaluate(bm)) is not None
    ]
    abnormal_finding_crud.bulk_create(db, finding_rows)
    finding_count = len(finding_rows)
    report_crud.set_status(db, report, progress=70)

    # Stage 4 — KB-grounded, safety-guarded explanations + overall summary + doctor questions
    # (one optional LLM call per report for the summary; per-finding prose is templated).
    user = user_crud.get_by_id(db, report.user_id)
    findings = abnormal_finding_crud.list_for_report(db, report.id)
    result = explanation_service.generate(report, biomarkers, findings, user)
    summary_crud.create(
        db,
        report_id=report.id,
        summary_text=result["overall_summary"],
        generation_mode=result["generation_mode"],
        model_used=result["model_used"],
    )
    for finding in findings:
        per = result["per_finding"].get(finding.biomarker_id)
        if per is not None:
            abnormal_finding_crud.set_explanation(
                db, finding.id, per["explanation"],
                json.dumps(per["citations"], ensure_ascii=False) if per["citations"] else None,
            )
    doctor_question_crud.bulk_create(db, report.id, result["doctor_questions"])

    report_crud.finalize_analyzed(db, report)
    logger.info(
        "Report %s analyzed (pages=%s, ocr_pages=%s, biomarkers=%s, findings=%s, mode=%s)",
        report.id, extraction.page_count, len(ocr_confidences), len(biomarkers),
        finding_count, result["generation_mode"],
    )
