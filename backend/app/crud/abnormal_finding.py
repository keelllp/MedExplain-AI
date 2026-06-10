"""Abnormal-finding data access (one finding per biomarker)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AbnormalFinding, Biomarker


def create(
    db: Session, *, biomarker_id: int, status: str, severity: str, direction: str,
    rule_id: str | None = None, explanation: str | None = None, citations_json: str | None = None,
) -> AbnormalFinding:
    finding = AbnormalFinding(
        biomarker_id=biomarker_id,
        status=status,
        severity=severity,
        direction=direction,
        rule_id=rule_id,
        explanation=explanation,
        citations_json=citations_json,
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def bulk_create(db: Session, items: list[dict]) -> None:
    """Insert all findings in one commit (atomic for the rules stage)."""
    objects = [AbnormalFinding(**item) for item in items]
    if not objects:
        return
    db.add_all(objects)
    db.commit()


def set_explanation(db: Session, finding_id: int, explanation: str, citations_json: str | None) -> None:
    finding = db.get(AbnormalFinding, finding_id)
    if finding is None:
        return
    finding.explanation = explanation
    finding.citations_json = citations_json
    db.commit()


def list_for_report(db: Session, report_id: int) -> list[AbnormalFinding]:
    return list(
        db.execute(
            select(AbnormalFinding)
            .join(Biomarker, AbnormalFinding.biomarker_id == Biomarker.id)
            .where(Biomarker.report_id == report_id)
            .order_by(AbnormalFinding.id)
        )
        .scalars()
        .all()
    )
