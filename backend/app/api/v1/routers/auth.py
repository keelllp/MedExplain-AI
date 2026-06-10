"""Authentication endpoints: register, login, me, change-password."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.exceptions import AuthError, ConflictError, ValidationAppError
from app.core.security import create_access_token, verify_password
from app.crud import user as user_crud
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut
from app.schemas.common import Message
from app.schemas.user import PasswordChangeIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> UserOut:
    # Per docs/04 §4.1: register returns the created UserOut (201); the client then
    # calls /auth/login to obtain a token. (No auto-login token on register.)
    if user_crud.get_by_email(db, body.email) is not None:
        raise ConflictError("An account with this email already exists.")
    user = user_crud.create_user(
        db, email=body.email, password=body.password, full_name=body.full_name
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.authenticate(db, email=body.email, password=body.password)
    if user is None:
        # Same message for unknown-email and wrong-password (no account enumeration).
        raise AuthError("Invalid email or password.")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post("/change-password", response_model=Message)
def change_password(
    body: PasswordChangeIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    if not verify_password(body.current_password, current_user.password_hash):
        raise AuthError("Current password is incorrect.")
    if verify_password(body.new_password, current_user.password_hash):
        raise ValidationAppError("New password must differ from the current password.")
    user_crud.change_password(db, current_user, body.new_password)
    return Message(message="Password updated.")
