"""Agent tool audit service — every tool call MUST be logged."""

from __future__ import annotations

from uuid import UUID

from structlog import get_logger

from backend.models.agent_tool_call import AgentToolCall

logger = get_logger(__name__)


class AgentToolAuditService:
    """Аудит всех вызовов инструментов агента.

    Каждый вызов (успех или неудача) записывается в agent_tool_calls.
    """

    def __init__(self, repo):
        self._repo = repo

    async def log_call(
        self,
        correlation_id: str,
        user_id: UUID,
        tool_name: str,
        duration_ms: float,
        success: bool,
        session_id: UUID | None = None,
        input_hash: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Записать вызов инструмента в audit log."""
        try:
            record = AgentToolCall(
                correlation_id=correlation_id,
                session_id=session_id,
                user_id=user_id,
                tool_name=tool_name,
                input_hash=input_hash,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message,
            )
            await self._repo.create(record)
        except Exception as e:
            logger.error("agent_audit_failed", tool_name=tool_name, error=str(e))
