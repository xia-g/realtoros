from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.task import Task
from backend.repositories.base import GenericRepository


class TaskRepository(GenericRepository[Task]):
    def __init__(self, session):
        super().__init__(session, Task)

    async def find_by_assignee(self, user_id: UUID) -> list[Task]:
        stmt = select(Task).where(Task.assigned_to == user_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_client(self, client_id: UUID) -> list[Task]:
        stmt = select(Task).where(Task.client_id == client_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_pending(self) -> list[Task]:
        stmt = select(Task).where(Task.status.in_(["new", "in_progress"]))
        stmt = self._active_filter(stmt).order_by(Task.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
