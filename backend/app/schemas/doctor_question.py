"""Doctor-question output schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.common import QuestionCategory


class DoctorQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    category: QuestionCategory
    ordering: int
