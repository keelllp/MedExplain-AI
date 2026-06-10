"""Logging configuration.

PII-safe by policy: application logs MUST NOT contain report text, biomarker
values, or LLM payloads. Log identifiers (ids), event types, and surfaces only.
"""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s :: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO if settings.is_prod else logging.DEBUG)

    # Quiet noisy third-party loggers (pdfminer is extremely verbose at DEBUG).
    for noisy in ("pdfminer", "pdfplumber", "PIL", "paddle", "ppocr"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
