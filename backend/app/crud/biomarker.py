"""Biomarker data access."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AbnormalFinding, Biomarker, Report


def bulk_insert(db: Session, report_id: int, raws) -> list[Biomarker]:
    objects = [
        Biomarker(
            report_id=report_id,
            test_name=r.test_name,
            canonical_name=r.canonical_name,
            value=r.value,
            value_text=r.value_text,
            unit=r.unit,
            canonical_unit=r.canonical_unit,
            reference_low=r.reference_low,
            reference_high=r.reference_high,
            reference_range_text=r.reference_range_text,
            captured_at=None,
        )
        for r in raws
    ]
    if not objects:
        return []
    db.add_all(objects)
    db.commit()
    # Re-query once (cheap) instead of refreshing each row; returns fresh, loaded objects.
    return list_for_report(db, report_id)


def delete_for_report(db: Session, report_id: int) -> None:
    """Remove a report's biomarkers (findings cascade via FK). Makes re-analyze idempotent."""
    db.execute(delete(Biomarker).where(Biomarker.report_id == report_id))
    db.commit()


def list_for_report(db: Session, report_id: int) -> list[Biomarker]:
    return list(
        db.execute(
            select(Biomarker).where(Biomarker.report_id == report_id).order_by(Biomarker.id)
        )
        .scalars()
        .all()
    )


# --- trends (Phase 8): one canonical biomarker across a user's reports, time-ordered ---

def trend_points(db: Session, user_id: int, canonical_name: str):
    """Numeric points for one canonical biomarker across the user's reports, oldest first.

    point_time = COALESCE(captured_at, uploaded_at); ties broken by report_id so same-day
    uploads keep a stable order. Left-joins the finding for per-point severity/direction.
    Resolves via idx_biomarkers_canonical_report (canonical_name, report_id)."""
    point_time = func.coalesce(Biomarker.captured_at, Report.uploaded_at).label("point_time")
    stmt = (
        select(
            Biomarker.report_id.label("report_id"),
            point_time,
            Biomarker.value.label("value"),
            Biomarker.unit.label("unit"),
            Biomarker.canonical_unit.label("canonical_unit"),
            Biomarker.reference_low.label("reference_low"),
            Biomarker.reference_high.label("reference_high"),
            AbnormalFinding.severity.label("severity"),
            AbnormalFinding.direction.label("direction"),
        )
        .join(Report, Report.id == Biomarker.report_id)
        .join(AbnormalFinding, AbnormalFinding.biomarker_id == Biomarker.id, isouter=True)
        .where(
            Report.user_id == user_id,
            Biomarker.canonical_name == canonical_name,
            Biomarker.value.is_not(None),
        )
        .order_by(point_time.asc(), Biomarker.report_id.asc())
    )
    return db.execute(stmt).all()


def trendable_biomarkers(db: Session, user_id: int):
    """Distinct canonical_names with >= 2 numeric points for this user (for the selector)."""
    point_time = func.coalesce(Biomarker.captured_at, Report.uploaded_at)
    stmt = (
        select(
            Biomarker.canonical_name.label("canonical_name"),
            func.count().label("count"),
            func.max(point_time).label("latest_point_time"),
        )
        .join(Report, Report.id == Biomarker.report_id)
        .where(
            Report.user_id == user_id,
            Biomarker.canonical_name.is_not(None),
            Biomarker.value.is_not(None),
        )
        .group_by(Biomarker.canonical_name)
        .having(func.count() >= 2)
        .order_by(func.max(point_time).desc())
    )
    return db.execute(stmt).all()
