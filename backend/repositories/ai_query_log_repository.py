"""AI query log repository — cost tracking and analytics."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from backend.models.ai_call_log import AIQueryLog
from backend.repositories.base import GenericRepository


class AIQueryLogRepository(GenericRepository[AIQueryLog]):
    def __init__(self, session):
        super().__init__(session, AIQueryLog)

    async def get_by_correlation(self, correlation_id: str) -> list[AIQueryLog]:
        stmt = select(AIQueryLog).where(
            AIQueryLog.correlation_id == correlation_id
        ).order_by(AIQueryLog.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_costs(self, user_id: UUID, since: datetime | None = None) -> float:
        stmt = select(func.coalesce(func.sum(AIQueryLog.cost_usd), 0)).where(
            AIQueryLog.user_id == user_id
        )
        if since:
            stmt = stmt.where(AIQueryLog.created_at >= since)
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def get_daily_cost(self, user_id: UUID | None = None) -> float:
        today = datetime.now(timezone.utc).date()
        stmt = select(func.coalesce(func.sum(AIQueryLog.cost_usd), 0)).where(
            cast(AIQueryLog.created_at, Date) == today
        )
        if user_id:
            stmt = stmt.where(AIQueryLog.user_id == user_id)
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0)

    async def get_provider_stats(self, provider: str) -> dict:
        total = select(func.count()).select_from(AIQueryLog).where(AIQueryLog.provider == provider)
        cost = select(func.coalesce(func.sum(AIQueryLog.cost_usd), 0)).where(AIQueryLog.provider == provider)
        avg_latency = select(func.coalesce(func.avg(AIQueryLog.latency_ms), 0)).where(AIQueryLog.provider == provider)
        t, c, l = await self.session.execute(total), await self.session.execute(cost), await self.session.execute(avg_latency)
        return {
            "total_calls": t.scalar() or 0,
            "total_cost": float(c.scalar() or 0),
            "avg_latency_ms": float(l.scalar() or 0),
        }