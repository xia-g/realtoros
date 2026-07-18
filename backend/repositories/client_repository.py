from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from backend.models.client import Client
from backend.repositories.base import GenericRepository


class ClientRepository(GenericRepository[Client]):
    def __init__(self, session):
        super().__init__(session, Client)

    async def find_by_phone(self, phone: str) -> Client | None:
        stmt = select(Client).where(Client.phone == phone)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Client | None:
        stmt = select(Client).where(Client.email == email)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_duplicates(self, client: Client) -> list[Client]:
        """Find potential duplicates by phone or email."""
        conditions = []
        if client.phone:
            conditions.append(Client.phone == client.phone)
        if client.email:
            conditions.append(Client.email == client.email)
        if not conditions:
            return []
        stmt = select(Client).where(
            Client.id != client.id,
            or_(*conditions),
        )
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_name(self, query: str, limit: int = 20) -> list[Client]:
        stmt = select(Client).where(Client.full_name.ilike(f"%{query}%"))
        stmt = self._active_filter(stmt).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
