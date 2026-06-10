"""Unit tests for password hashing and JWT handling (no DB, no network)."""

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password!")
    assert hashed != "s3cret-password!"
    assert verify_password("s3cret-password!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_over_72_bytes_is_handled():
    # bcrypt only uses the first 72 bytes; must not raise and must verify.
    long_pw = "a" * 200
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)


def test_token_roundtrip_and_contains_no_phi():
    token = create_access_token(42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    # Only id/timestamps/type — no email or other PHI in the token.
    assert set(payload.keys()) <= {"sub", "iat", "exp", "type"}


def test_token_rejects_wrong_secret():
    token = create_access_token(1)
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "the-wrong-secret", algorithms=[settings.jwt_algorithm])
