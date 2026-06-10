from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_iso


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)

    # LLM generation policy (see docs/03 + docs/07). Default privacy-first 'offline'.
    llm_mode: Mapped[str] = mapped_column(String, nullable=False, default="offline")
    gemini_consent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gemini_consented_at: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(
        String, nullable=False, default=utcnow_iso, onupdate=utcnow_iso
    )
