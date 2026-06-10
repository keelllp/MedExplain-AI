"""Chat schemas (docs/04 §4.12–§4.15).

Chat is a separate single LLM call per user message that reuses the Phase 5 safety
guard, LLM router, and KB retrieval. Assistant turns are guarded prose (the disclaimer
is embedded) and carry RAG citations in the ``{doc, chunk_id, score}`` form that mirrors
``chat_messages.citations_json`` (distinct from the per-marker explanation citation form).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import DISCLAIMER, GenerationMode


class ChatCitation(BaseModel):
    """Mirrors chat_messages.citations_json shape ({doc, chunk_id, score})."""

    doc: str
    chunk_id: str
    score: float


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[int] = Field(default=None, gt=0)  # omit to start a new session
    report_id: Optional[int] = Field(default=None, gt=0)    # scope RAG to this report


class ChatResponse(BaseModel):
    session_id: int
    message_id: int            # id of the persisted assistant turn
    answer: str                # guarded prose (disclaimer embedded)
    citations: list[ChatCitation] = []
    refused: bool = False
    generation_mode: GenerationMode
    disclaimer: str = DISCLAIMER


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: Optional[int] = None   # null = general educational chat
    title: str
    created_at: str
    updated_at: str


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str                        # assistant turns are guarded prose
    citations: list[ChatCitation] = []  # populated on assistant turns from citations_json
    created_at: str
