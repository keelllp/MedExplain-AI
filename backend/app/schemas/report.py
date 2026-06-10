"""Report / file schemas (Phase 3 surface, per docs/04 §4.8–§4.11).

biomarkers / findings / summary / doctor_questions are populated in Phases 4–5; in
Phase 3 they serialize as empty arrays / null (matching the frozen ReportDetailOut).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.biomarker import AbnormalFindingOut, BiomarkerOut
from app.schemas.common import DISCLAIMER, ErrorCode, ReportStatus, ReportType
from app.schemas.doctor_question import DoctorQuestionOut
from app.schemas.summary import SummaryOut


class ReportUploadResponse(BaseModel):
    report_id: int
    status: ReportStatus
    original_filename: str
    mime_type: str
    size_bytes: int


class AnalyzeIn(BaseModel):
    report_id: int = Field(gt=0)


class AnalyzeAcceptedResponse(BaseModel):
    report_id: int
    status: ReportStatus
    progress: int


class ReportSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: ReportType
    status: ReportStatus
    progress: int
    error_code: ErrorCode | None = None
    ocr_confidence: float | None = None
    uploaded_at: str
    analyzed_at: str | None = None


class ReportDetailOut(BaseModel):
    id: int
    title: str
    report_type: ReportType
    status: ReportStatus
    progress: int
    error_code: ErrorCode | None = None
    ocr_confidence: float | None = None
    uploaded_at: str
    analyzed_at: str | None = None
    biomarkers: list[BiomarkerOut] = []
    findings: list[AbnormalFindingOut] = []
    summary: SummaryOut | None = None
    doctor_questions: list[DoctorQuestionOut] = []
    disclaimer: str = DISCLAIMER
