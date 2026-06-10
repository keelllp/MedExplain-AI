"""Trend endpoints (Phase 8): one biomarker's numeric series across the caller's reports.

`GET /trends?biomarker=<canonical_name>` returns the time-ordered points + a deterministic
improving/worsening/stable label (data-only; no generated prose). `GET /trends/biomarkers`
lists the canonical names that have >= 2 numeric points (the dashboard selector). All reads
are owner-scoped via the JWT user_id. See docs/04-api-spec.md §4.16.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.crud import biomarker as biomarker_crud
from app.models import User
from app.schemas.trend import TrendableBiomarker, TrendResponse
from app.services import trend_service

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/biomarkers", response_model=list[TrendableBiomarker])
def list_trendable(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrendableBiomarker]:
    rows = biomarker_crud.trendable_biomarkers(db, current_user.id)
    return [
        TrendableBiomarker(
            canonical_name=r.canonical_name,
            display=trend_service.display_name(r.canonical_name),
            count=r.count,
            latest_point_time=r.latest_point_time,
        )
        for r in rows
    ]


@router.get("", response_model=TrendResponse)
def get_trends(
    biomarker: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrendResponse:
    rows = biomarker_crud.trend_points(db, current_user.id, biomarker)
    display, points, trend = trend_service.build(biomarker, rows)
    return TrendResponse(biomarker=biomarker, display=display, points=points, trend=trend)
