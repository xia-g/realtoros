"""Budget usage repository — PostgreSQL-backed cost tracking with SELECT FOR UPDATE."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.models.budget_usage import BudgetUsage
from backend.repositories.base import GenericRepository


class BudgetUsageRepository(GenericRepository[BudgetUsage]):
    def __init__(self, session):
        super().__init__(session, BudgetUsage)

    async def get_or_create(self, user_id: UUID | None, day: date) -> BudgetUsage:
        stmt = select(BudgetUsage).where(
            BudgetUsage.user_id == user_id,
            BudgetUsage.day == day,
        ).with_for_update()
        result = await self.session.execute(stmt)
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = BudgetUsage(user_id=user_id, day=day, spent_usd=0.0)
            self.session.add(usage)
            await self.session.flush()
        return usage

    async def reserve_and_check(self, user_id: UUID | None, amount: float,
                                 daily_limit: float) -> bool:
        """Atomically reserve budget. Returns True if within limit."""
        today = datetime.now(timezone.utc).date()
        usage = await self.get_or_create(user_id, today)
        if (usage.spent_usd or 0.0) + amount > daily_limit:
            return False
        usage.spent_usd = (usage.spent_usd or 0.0) + amount
        await self.session.flush()
        return True

    async def adjust(self, user_id: UUID | None, old_est: float, new_actual: float) -> None:
        """Adjust budget after actual cost is known."""
        today = datetime.now(timezone.utc).date()
        stmt = select(BudgetUsage).where(
            BudgetUsage.user_id == user_id,
            BudgetUsage.day == day,
        ).with_for_update()
        result = await self.session.execute(stmt)
        usage = result.scalar_one_or_none()
        if usage:
            diff = new_actual - old_est
            usage.spent_usd = (usage.spent_usd or 0.0) + diff
            await self.session.flush()

    async def get_daily_spent(self, user_id: UUID | None) -> float:
        today = datetime.now(timezone.utc).date()
        stmt = select(func.coalesce(BudgetUsage.spent_usd, 0.0)).where(
            BudgetUsage.user_id == user_id,
            BudgetUsage.day == today,
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0.0)