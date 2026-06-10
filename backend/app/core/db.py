"""SQLAlchemy engine, session factory, and the FastAPI DB dependency.

The ``connect`` event listener applies the per-connection SQLite PRAGMAs the
schema relies on (``foreign_keys`` is OFF by default in SQLite and must be set on
*every* connection). The backend runs as a single Uvicorn worker (``--workers 1``),
so there is exactly one process holding connections — matching the schema's
single-writer assumptions.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# check_same_thread=False: SQLite connections may be used across FastAPI's threadpool.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    class_=Session,
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
