"""User / account schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import LLMMode


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    llm_mode: LLMMode
    gemini_consent: bool  # coerced from the stored 0/1 integer
    gemini_consented_at: str | None = None
    created_at: str
    updated_at: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)


class SettingsUpdate(BaseModel):
    """Update generation policy. Setting ``cloud`` records Gemini egress consent."""

    llm_mode: LLMMode


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
