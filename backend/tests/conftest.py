"""Pytest fixtures. Run from the backend/ directory with: python -m pytest

The DB path + config are isolated to a temp dir BEFORE the app is imported, so the
cached Settings singleton picks up the test database (never the real data/ DB).
"""

import os
import tempfile
from pathlib import Path

# --- isolate config/DB before importing the app ---
_TMPDIR = tempfile.mkdtemp(prefix="medexplain_test_")
os.environ["MEDEXPLAIN_DB_PATH"] = str(Path(_TMPDIR) / "test.db")
os.environ["MEDEXPLAIN_ENV"] = "dev"
os.environ["MEDEXPLAIN_JWT_SECRET"] = "test-secret-not-for-production-0123456789abcdef"
os.environ["MEDEXPLAIN_GEMINI_API_KEY"] = ""  # cloud mode unavailable in tests
os.environ["MEDEXPLAIN_OLLAMA_HOST"] = "http://127.0.0.1:9"  # dead port → deterministic offline-template
# Pin the new-account default to offline for the suite (production defaults to 'cloud'); this
# keeps the privacy-first registration assertions decoupled from the deployment policy.
os.environ["MEDEXPLAIN_DEFAULT_LLM_MODE"] = "offline"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture()
def client(app):
    # Entering the TestClient context runs the lifespan startup (init_db + reconcile).
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(client):
    """A direct DB session. Depends on `client` so the schema is initialized."""
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
