"""Generic repository pattern with async CRUD and soft delete support.

All entity repositories inherit from GenericRepository.
Soft delete: list/get exclude deleted records; delete() sets deleted_at.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import Base


class GenericRepository[T: Base]:
    """Generic async repository for SQLAlchemy models with soft delete."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    def _active_filter(self, stmt):
        """Add soft-delete filter if model has deleted_at column."""
        if hasattr(self.model, "deleted_at"):
            return stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get(self, id: UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        filters: dict | None = None,
        order_by: str | None = None,
        descending: bool = False,
    ) -> tuple[list[T], int]:
        stmt = select(self.model)
        stmt = self._active_filter(stmt)

        if filters:
            for field, value in filters.items():
                column = getattr(self.model, field, None)
                if column is not None:
                    stmt = stmt.where(column == value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        if order_by:
            column = getattr(self.model, order_by, None)
            if column is not None:
                stmt = stmt.order_by(column.desc() if descending else column.asc())

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def update(self, id: UUID, **kwargs) -> T | None:
        instance = await self.get(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, id: UUID) -> bool:
        """Soft delete: set deleted_at instead of removing."""
        instance = await self.get(id)
        if instance is None:
            return False
        if hasattr(instance, "deleted_at"):
            instance.deleted_at = datetime.now(timezone.utc)
            await self.session.flush()
            return True
        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def hard_delete(self, id: UUID) -> bool:
        """Permanent deletion (admin only)."""
        instance = await self.session.get(self.model, id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def restore(self, id: UUID) -> T | None:
        """Restore a soft-deleted entity by clearing deleted_at."""
        instance = await self.session.get(self.model, id)
        if instance is None:
            return None
        if hasattr(instance, "deleted_at") and instance.deleted_at is not None:
            instance.deleted_at = None
            await self.session.flush()
        return instance

    async def exists(self, **filters) -> bool:
        """Check if a record matching all filters exists (including soft-deleted)."""
        stmt = select(self.model).where(
            *[getattr(self.model, k) == v for k, v in filters.items()]
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count(self, **filters) -> int:
        """Count records matching optional filters."""
        stmt = select(func.count()).select_from(self.model)
        for field, value in filters.items():
            column = getattr(self.model, field, None)
            if column is not None:
                stmt = stmt.where(column == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
