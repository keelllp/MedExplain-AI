"""Startup reconciler: recover reports left stuck mid-analysis by a crash.

Because the backend is a single worker with a concurrency cap of 1, nothing is
legitimately ``processing`` at boot — so any such row is a crash artifact and is
marked ``failed`` with an enumerated ``timeout`` code (never raw error text).
"""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Report, utcnow_iso

logger = get_logger(__name__)


def reconcile_stuck_reports(db: Session) -> int:
    stmt = (
        update(Report)
        .where(Report.status == "processing")
        .values(status="failed", error_code="timeout", updated_at=utcnow_iso())
    )
    result = db.execute(stmt)
    db.commit()
    count = result.rowcount or 0
    if count:
        logger.info("Reconciler marked %d stuck report(s) as failed", count)
    return count
