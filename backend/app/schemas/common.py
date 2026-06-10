"""Shared enums and envelope models. Enums mirror the DB CHECK constraints."""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

# The mandatory safety sentence. Server-side guards (Phase 5) guarantee it is present
# on every explanatory response; defined here so all layers reference one constant.
DISCLAIMER = "Consult a licensed healthcare professional for medical advice."


class ReportStatus(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    analyzed = "analyzed"
    failed = "failed"


class ReportType(str, Enum):
    blood = "blood"
    cbc = "cbc"
    mri = "mri"
    ct = "ct"
    xray = "xray"
    pathology = "pathology"
    prescription = "prescription"
    discharge = "discharge"
    other = "other"


class Severity(str, Enum):
    normal = "normal"
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


class Direction(str, Enum):
    low = "low"
    high = "high"
    normal = "normal"


class LLMMode(str, Enum):
    cloud = "cloud"
    offline = "offline"


class GenerationMode(str, Enum):
    gemini = "gemini"
    ollama = "ollama"
    offline_template = "offline_template"


class ErrorCode(str, Enum):
    """Sanitized, enumerated report failure codes (never raw exception text / PHI)."""

    ocr_failed = "ocr_failed"
    extraction_failed = "extraction_failed"
    llm_unavailable = "llm_unavailable"
    timeout = "timeout"
    internal_error = "internal_error"


class QuestionCategory(str, Enum):
    cause = "cause"
    follow_up = "follow-up"
    clarification = "clarification"


class ChatRole(str, Enum):
    user = "user"
    assistant = "assistant"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None  # noqa: UP045  (kept Optional for py3.10 eval safety)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Message(BaseModel):
    message: str


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
