from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.deal import Deal
from backend.repositories.base import GenericRepository


class DealRepository(GenericRepository[Deal]):
    def __init__(self, session):
        super().__init__(session, Deal)

    async def find_active(self) -> list[Deal]:
        stmt = select(Deal).where(Deal.status.notin_(["closed", "cancelled"]))
        stmt = self._active_filter(stmt).order_by(Deal.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_client(self, client_id: UUID) -> list[Deal]:
        from backend.models.deal_participant import DealParticipant
        stmt = (
            select(Deal)
            .join(DealParticipant)
            .where(DealParticipant.client_id == client_id)
        )
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_property(self, property_id: UUID) -> list[Deal]:
        stmt = select(Deal).where(Deal.property_id == property_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
