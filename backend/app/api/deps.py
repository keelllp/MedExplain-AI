"""Shared FastAPI dependencies (auth)."""

from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import AuthError
from app.core.security import decode_access_token
from app.crud import user as user_crud
from app.models import User

# auto_error=False so we return our own enveloped 401 (not Starlette's {"detail": ...}).
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthError("Missing bearer token.")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token.") from exc

    # Reject non-access tokens (e.g. future refresh/reset tokens signed with the same key).
    if payload.get("type") != "access":
        raise AuthError("Invalid token type.")

    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise AuthError("Invalid token subject.") from exc

    user = user_crud.get_by_id(db, user_id)
    if user is None:
        raise AuthError("User no longer exists.")
    return user
