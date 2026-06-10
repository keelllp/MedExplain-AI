"""Unit tests for the startup config guards in Settings.validate_runtime()."""

import pytest

from app.core.config import _DEFAULT_DEV_SECRET, Settings

pytestmark = pytest.mark.unit

_STRONG = "a-strong-secret-of-more-than-32-bytes-1234567890"
_OK_ORIGINS = "http://localhost:3000"


def test_prod_refuses_default_jwt_secret():
    s = Settings(env="prod", jwt_secret=_DEFAULT_DEV_SECRET, cors_origins=_OK_ORIGINS)
    with pytest.raises(RuntimeError, match="default JWT secret"):
        s.validate_runtime()


def test_prod_ok_with_strong_secret():
    s = Settings(env="prod", jwt_secret=_STRONG, cors_origins=_OK_ORIGINS)
    s.validate_runtime()  # must not raise


def test_dev_tolerates_default_secret():
    s = Settings(env="dev", jwt_secret=_DEFAULT_DEV_SECRET, cors_origins=_OK_ORIGINS)
    s.validate_runtime()  # dev is allowed to use the default secret


def test_wildcard_cors_is_rejected():
    s = Settings(env="dev", jwt_secret=_STRONG, cors_origins="*")
    with pytest.raises(RuntimeError, match="CORS"):
        s.validate_runtime()


def test_gemini_available_reflects_key():
    assert Settings(gemini_api_key="").gemini_available is False
    assert Settings(gemini_api_key="some-key").gemini_available is True
