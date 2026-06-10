"""ORM models for MedExplain AI's 9 tables.

Importing this package registers every model on ``Base.metadata``. The tables
themselves are created from the canonical ``app/db/init.sql`` (not ``create_all``);
these models map onto that schema for typed ORM access.
"""

from __future__ import annotations

from app.models.abnormal_finding import AbnormalFinding
from app.models.base import Base, utcnow_iso
from app.models.biomarker import Biomarker
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.doctor_question import DoctorQuestion
from app.models.report import Report
from app.models.report_file import ReportFile
from app.models.summary import Summary
from app.models.user import User

__all__ = [
    "Base",
    "utcnow_iso",
    "User",
    "Report",
    "ReportFile",
    "Biomarker",
    "AbnormalFinding",
    "Summary",
    "DoctorQuestion",
    "ChatSession",
    "ChatMessage",
]
