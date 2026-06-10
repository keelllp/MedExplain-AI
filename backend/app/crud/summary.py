"""Summary data access (latest-per-report overall summary)."""

from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models import Summary


def create(db: Session, *, report_id: int, summary_text: str, generation_mode: str, model_used: str) -> Summary:
    summary = Summary(
        report_id=report_id,
        summary_text=summary_text,
        generation_mode=generation_mode,
        model_used=model_used,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def get_latest_for_report(db: Session, report_id: int) -> Summary | None:
    return (
        db.execute(
            select(Summary)
            .where(Summary.report_id == report_id)
            .order_by(desc(Summary.generated_at), desc(Summary.id))
        )
        .scalars()
        .first()
    )


def delete_for_report(db: Session, report_id: int) -> None:
    db.execute(delete(Summary).where(Summary.report_id == report_id))
    db.commit()
