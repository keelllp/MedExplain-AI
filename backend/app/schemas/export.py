"""Export schemas (docs/04 §4.17).

POST /export streams a PDF summary of an analyzed report with the full disclaimer block on
every page. Raw chat is excluded by default (D-EXPORT-CHAT); if included, each chat turn is
re-passed through the output guard before embedding.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    report_id: int = Field(gt=0)
    include_chat: bool = False  # default excludes raw chat (D-EXPORT-CHAT)
