"""Application exceptions and a consistent JSON error envelope.

Every error response has the shape::

    {"error": {"code": "<machine_code>", "message": "<human message>", "details": <optional>}}

Handlers are registered on the app in ``main.py`` via ``register_exception_handlers``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        if message:
            self.message = message
        self.details = details
        super().__init__(self.message)


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required or invalid."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have access to this resource."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource conflict."


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Request validation failed."


def error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


_HTTP_CODE_MAP = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
    501: "not_implemented",
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request, exc: AppError):  # noqa: ANN001
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_request, exc: RequestValidationError):  # noqa: ANN001
        # Shape per docs/04 §1.3: details is a list of {field, issue}. loc[0] is the
        # request part ("body"/"query"/...); we drop it and join the rest as a path.
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"][1:]) or None,
                "issue": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_request, exc: StarletteHTTPException):  # noqa: ANN001
        code = _HTTP_CODE_MAP.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(_request, exc: Exception):  # noqa: ANN001
        # Never leak internal details (or PHI) to the client.
        logger.exception("Unhandled %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred."),
        )
