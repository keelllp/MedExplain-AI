"""Doctor-question data access."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DoctorQuestion


def bulk_create(db: Session, report_id: int, items: list[dict]) -> None:
    objects = [
        DoctorQuestion(
            report_id=report_id,
            question_text=item["question_text"],
            category=item["category"],
            ordering=item["ordering"],
        )
        for item in items
    ]
    if not objects:
        return
    db.add_all(objects)
    db.commit()


def list_for_report(db: Session, report_id: int) -> list[DoctorQuestion]:
    return list(
        db.execute(
            select(DoctorQuestion)
            .where(DoctorQuestion.report_id == report_id)
            .order_by(DoctorQuestion.ordering, DoctorQuestion.id)
        )
        .scalars()
        .all()
    )


def delete_for_report(db: Session, report_id: int) -> None:
    db.execute(delete(DoctorQuestion).where(DoctorQuestion.report_id == report_id))
    db.commit()
