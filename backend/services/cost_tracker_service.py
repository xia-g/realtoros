"""Budget control — PostgreSQL-backed cost tracking with SELECT FOR UPDATE.

Cross-process safe. Supports multiple workers, Telegram + API sharing budget.
Falls back to in-memory only if no session provided (single-process dev mode).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.core.logging import get_logger

logger = get_logger("app")

BUDGET_GLOBAL_DAILY: float = 10.0
BUDGET_USER_DAILY: float = 1.0


class CostTracker:
    """Budget tracker with PostgreSQL SELECT FOR UPDATE locking.

    Thread/process safe. Use across multiple workers, Telegram + API.
    Falls back to in-memory when no session provided.
    """

    def __init__(self, session=None, global_budget: float = BUDGET_GLOBAL_DAILY,
                 user_budget: float = BUDGET_USER_DAILY):
        self.session = session
        self.global_budget = global_budget
        self.user_budget = user_budget
        # In-memory fallback (single process dev mode)
        self._mem_spent: dict[str, float] = {}
        import asyncio
        self._mem_locks: dict[str, asyncio.locks.Lock] = {}
        self._dict_lock = None

    async def _repo(self):
        from backend.repositories.budget_usage_repository import BudgetUsageRepository
        if self.session:
            return BudgetUsageRepository(self.session)
        return None

    async def check_and_reserve(self, user_id: str, estimated_cost: float) -> bool:
        repo = await self._repo()
        if repo and self.session:
            # PostgreSQL path: SELECT FOR UPDATE
            uid = UUID(user_id) if user_id and len(user_id) == 36 else None
            try:
                global_ok = await repo.reserve_and_check(None, estimated_cost * 0.5, self.global_budget)
                if not global_ok:
                    logger.warning("budget_global_exceeded", user_id=user_id, estimated=estimated_cost)
                    return False
                if uid:
                    user_ok = await repo.reserve_and_check(uid, estimated_cost, self.user_budget)
                    if not user_ok:
                        logger.warning("budget_user_exceeded", user_id=user_id, estimated=estimated_cost)
                        return False
                return True
            except Exception as e:
                logger.exception("budget_db_error", error=str(e))
                return False

        # In-memory fallback
        import asyncio
        async with self._get_mem_lock("global"):
            spent = self._mem_spent.get("global", 0.0)
            if spent + estimated_cost > self.global_budget:
                return False
            self._mem_spent["global"] = spent + estimated_cost
        if uid:
            async with self._get_mem_lock(f"user:{user_id}"):
                spent = self._mem_spent.get(f"user:{user_id}", 0.0)
                if spent + estimated_cost > self.user_budget:
                    async with self._get_mem_lock("global"):
                        self._mem_spent["global"] -= estimated_cost
                    return False
                self._mem_spent[f"user:{user_id}"] = spent + estimated_cost
        return True

    async def record_actual(self, user_id: str, actual_cost: float, estimated_cost: float = 0.0) -> None:
        repo = await self._repo()
        if repo and self.session:
            uid = UUID(user_id) if user_id and len(user_id) == 36 else None
            try:
                await repo.adjust(None, estimated_cost * 0.5, actual_cost * 0.5)
                if uid:
                    await repo.adjust(uid, estimated_cost, actual_cost)
                return
            except Exception:
                pass
        # In-memory fallback
        diff = actual_cost - estimated_cost
        if diff != 0:
            async with self._get_mem_lock("global"):
                self._mem_spent["global"] = self._mem_spent.get("global", 0.0) + diff
            if uid:
                async with self._get_mem_lock(f"user:{user_id}"):
                    self._mem_spent[f"user:{user_id}"] = self._mem_spent.get(f"user:{user_id}", 0.0) + diff

    def _get_mem_lock(self, key: str):
        import asyncio
        if key not in self._mem_locks:
            self._mem_locks[key] = asyncio.locks.Lock()
        return self._mem_locks[key]

    async def get_spent(self, user_id: str | None = None) -> float:
        repo = await self._repo()
        if repo and self.session:
            uid = UUID(user_id) if user_id and len(user_id) == 36 else None
            return await repo.get_daily_spent(uid)
        if user_id:
            return self._mem_spent.get(f"user:{user_id}", 0.0)
        return self._mem_spent.get("global", 0.0)