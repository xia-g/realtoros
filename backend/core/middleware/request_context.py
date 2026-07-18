"""ASGI middleware that injects request context into every request.

Creates request_id, correlation_id, and starts a timer.
Sets X-Request-ID and X-Correlation-ID response headers.
"""

from __future__ import annotations

import time
import uuid

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.core.context.request_context import (
    RequestContext,
    reset_request_context,
    set_request_context,
)
from backend.core.logging import get_logger

logger = get_logger("app")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for request context injection."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        correlation_id = (
            request.headers.get("X-Correlation-ID") or uuid.uuid4().hex[:16]
        )

        ctx = RequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
        )
        set_request_context(ctx)

        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            reset_request_context()
            raise

        elapsed_ms = (time.time() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        logger.info(
            "request_completed",
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(elapsed_ms, 2),
        )

        reset_request_context()
        return response
