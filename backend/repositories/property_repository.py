from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from backend.models.property import Property
from backend.repositories.base import GenericRepository


class PropertyRepository(GenericRepository[Property]):
    def __init__(self, session):
        super().__init__(session, Property)

    async def find_by_owner(self, owner_id: UUID) -> list[Property]:
        stmt = select(Property).where(Property.owner_id == owner_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(self, status: str) -> list[Property]:
        stmt = select(Property).where(Property.status == status)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_text(self, query: str, limit: int = 20) -> list[Property]:
        pattern = f"%{query}%"
        stmt = (
            select(Property)
            .where(
                or_(
                    Property.address.ilike(pattern),
                    Property.title.ilike(pattern),
                    Property.description.ilike(pattern),
                )
            )
            .limit(limit)
        )
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
