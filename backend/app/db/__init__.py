"""Database bootstrap: create the schema from the canonical init.sql.

We deliberately do NOT use ``Base.metadata.create_all`` — ``init.sql`` is the single
source of truth (it carries CHECK constraints and indexes that are easiest to express
and audit as raw DDL). The ORM models map onto the tables this creates.
"""

from __future__ import annotations

from pathlib import Path

import app.models  # noqa: F401  -- registers all models on Base.metadata
from app.core.config import settings
from app.core.db import engine
from app.core.logging import get_logger

logger = get_logger(__name__)

_INIT_SQL = Path(__file__).resolve().parent / "init.sql"


def init_db() -> None:
    """Idempotently create the database file and all tables/indexes."""
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    sql = _INIT_SQL.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.executescript(sql)  # sqlite3 supports multi-statement scripts
        cursor.close()
        raw.commit()
    finally:
        raw.close()
    logger.info("Database initialized at %s", settings.db_file)
