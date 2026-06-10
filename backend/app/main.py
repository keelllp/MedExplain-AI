"""FastAPI application factory and startup wiring.

Startup (lifespan): configure logging, validate config, create the DB from
init.sql, and run the crash reconciler. The app exposes the v1 API under
``/api/v1`` and interactive docs at ``/docs``.

MedExplain AI is an EDUCATIONAL tool — it never diagnoses, treats, prescribes, or
doses. The mandatory disclaimer is enforced server-side on every explanatory
response (the safety guard lands in Phase 5).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db import init_db
from app.db.reconcile import reconcile_stuck_reports

logger = get_logger(__name__)

DESCRIPTION = (
    "Local, CPU-only educational assistant that helps users understand medical "
    "reports. It does not diagnose, treat, prescribe, or advise on dosages. "
    "Always consult a licensed healthcare professional for medical advice."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.validate_runtime()
    init_db()
    db = SessionLocal()
    try:
        reconcile_stuck_reports(db)
    finally:
        db.close()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    if settings.ocr_warmup:
        from app.services import ocr_service

        ocr_service.warm_up()
    logger.info("MedExplain AI backend started (env=%s)", settings.env)
    yield
    logger.info("MedExplain AI backend shutting down")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="MedExplain AI API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": app.version, "env": settings.env}

    return app


app = create_app()
