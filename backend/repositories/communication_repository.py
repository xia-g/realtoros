from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from backend.models.communication import Communication
from backend.repositories.base import GenericRepository


class CommunicationRepository(GenericRepository[Communication]):
    def __init__(self, session):
        super().__init__(session, Communication)

    async def find_by_client(self, client_id: UUID) -> list[Communication]:
        stmt = select(Communication).where(Communication.client_id == client_id)
        stmt = self._active_filter(stmt).order_by(Communication.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_deal(self, deal_id: UUID) -> list[Communication]:
        stmt = select(Communication).where(Communication.deal_id == deal_id)
        stmt = self._active_filter(stmt).order_by(Communication.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_assignee(self, user_id: UUID) -> list[Communication]:
        stmt = select(Communication).where(Communication.assigned_to == user_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
