"""Account/profile endpoints: update profile, update LLM settings, delete account."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import ForbiddenError
from app.crud import user as user_crud
from app.models import User
from app.schemas.common import LLMMode, Message
from app.schemas.user import SettingsUpdate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    # PATCH semantics: only fields actually present in the body are updated
    # (an omitted full_name must NOT wipe the stored value).
    user = user_crud.update_profile(db, current_user, body.model_dump(exclude_unset=True))
    return UserOut.model_validate(user)


@router.patch("/me/settings", response_model=UserOut)
def update_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    # Cloud mode is only selectable when the server actually has a Gemini key.
    if body.llm_mode == LLMMode.cloud and not settings.gemini_available:
        # Per docs/04 §4.6: a not-permitted action is 403 forbidden (not 422).
        raise ForbiddenError("Cloud mode is not available on this server.")
    user = user_crud.set_llm_mode(db, current_user, llm_mode=body.llm_mode.value)
    return UserOut.model_validate(user)


@router.delete("/me", response_model=Message)
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    user_crud.delete_user(db, current_user)
    return Message(message="Account and all associated data deleted.")
