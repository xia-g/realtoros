"""Request-scoped context using ContextVar.

Provides request_id, correlation_id, user_id, tenant_id, and started_at
for every API request. Accessible from any layer without passing through
function signatures.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# The ContextVar holds the current request context (or None outside a request).
_context_var: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)


class RequestContext:
    """Immutable request-scoped context.

    Created once per request by RequestContextMiddleware.
    Readable from any layer via get_request_context().
    """

    def __init__(
        self,
        request_id: str | None = None,
        correlation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        self.request_id = request_id or uuid.uuid4().hex[:16]
        self.correlation_id = correlation_id or uuid.uuid4().hex[:16]
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.started_at = started_at or datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


def get_request_context() -> RequestContext | None:
    """Get the current request context.

    Returns None if called outside a request context (e.g., startup, background task).
    """
    return _context_var.get()


def set_request_context(ctx: RequestContext) -> None:
    """Set the current request context (called by middleware)."""
    _context_var.set(ctx)


def reset_request_context() -> None:
    """Reset the context var to None (called after request completes)."""
    _context_var.set(None)
