"""Audit context for future audit middleware.

Captures request metadata needed for audit logging without
touching the database. Preparation for Sprint 2 (T12).
"""

from __future__ import annotations

from backend.core.context import get_request_context


class AuditContext:
    """Request metadata for audit logging.

    Populated by future audit middleware from request headers
    and context. No DB writes yet.
    """

    def __init__(
        self,
        request_id: str,
        correlation_id: str | None = None,
        user_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        source_component: str = "api",
    ) -> None:
        self.request_id = request_id
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.source_ip = source_ip
        self.user_agent = user_agent
        self.source_component = source_component

    def to_dict(self) -> dict[str, str | None]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "source_component": self.source_component,
        }


def get_audit_context() -> AuditContext:
    """Build an AuditContext from the current request context."""
    ctx = get_request_context()
    return AuditContext(
        request_id=ctx.request_id if ctx else "unknown",
        correlation_id=ctx.correlation_id if ctx else None,
        user_id=ctx.user_id if ctx else None,
    )
