"""Aggregate all v1 routers. Mounted by main.py under the /api/v1 prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import auth, chat, export, reports, trends, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(reports.router)
api_router.include_router(chat.router)
api_router.include_router(trends.router)
api_router.include_router(export.router)
