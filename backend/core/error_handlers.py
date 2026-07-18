"""Global FastAPI exception handlers.

All exceptions are logged through structlog and returned as
structured JSON error responses.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import AppError
from backend.core.logging import get_logger

logger = get_logger("app")


def register_error_handlers(app: FastAPI) -> None:
    """Register all global error handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.error(
            "app_error",
            code=exc.code,
            message=exc.message,
            details=exc.details,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=_http_status(exc.code),
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_error",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )


def _http_status(code: str) -> int:
    """Map error code to HTTP status."""
    mapping = {
        "VALIDATION_ERROR": 422,
        "NOT_FOUND": 404,
        "CONFLICT": 409,
        "FORBIDDEN": 403,
        "UNAUTHORIZED": 401,
        "LEAD_STATE_ERROR": 409,
        "DUPLICATE_ENTITY": 409,
    }
    return mapping.get(code, 500)
