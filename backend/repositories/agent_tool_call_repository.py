"""Agent tool call repository — audit log persistence."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.agent_tool_call import AgentToolCall
from backend.repositories.generic_repository import GenericRepository


class AgentToolCallRepository(GenericRepository[AgentToolCall]):
    def __init__(self, session):
        super().__init__(session, AgentToolCall)

    async def create(self, tool_call: AgentToolCall) -> AgentToolCall:
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def list_by_session(self, session_id: UUID, limit: int = 50) -> list[AgentToolCall]:
        result = await self.session.execute(
            select(AgentToolCall)
            .where(AgentToolCall.session_id == session_id)
            .order_by(AgentToolCall.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_correlation(self, correlation_id: str) -> list[AgentToolCall]:
        result = await self.session.execute(
            select(AgentToolCall)
            .where(AgentToolCall.correlation_id == correlation_id)
            .order_by(AgentToolCall.created_at.asc())
        )
        return list(result.scalars().all())
