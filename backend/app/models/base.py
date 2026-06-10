"""Declarative base for all ORM models.

Kept in its own module so model modules can import ``Base`` without creating an
import cycle through ``app.models.__init__`` (which imports every model).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 'Z' string, matching the schema's text timestamps."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
