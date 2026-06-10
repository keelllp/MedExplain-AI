"""Summary output schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import GenerationMode


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary_text: str
    generation_mode: GenerationMode
    model_used: str  # NOT NULL column; always set by the generator
    generated_at: str
