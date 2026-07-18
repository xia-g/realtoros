from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from backend.models.lead import Lead
from backend.repositories.base import GenericRepository


class LeadRepository(GenericRepository[Lead]):
    def __init__(self, session):
        super().__init__(session, Lead)

    async def find_by_source(self, source: str, source_id: str) -> Lead | None:
        stmt = select(Lead).where(
            Lead.source == source,
            Lead.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_phone(self, phone: str) -> list[Lead]:
        stmt = select(Lead).where(Lead.phone == phone)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_duplicates(self, lead: Lead) -> list[Lead]:
        """Find potential duplicates by phone, email, or telegram_id."""
        conditions = []
        if lead.phone:
            conditions.append(Lead.phone == lead.phone)
        if lead.email:
            conditions.append(Lead.email == lead.email)
        if lead.telegram_id:
            conditions.append(Lead.telegram_id == lead.telegram_id)
        if not conditions:
            return []
        stmt = select(Lead).where(
            Lead.id != lead.id,
            or_(*conditions),
        )
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_active_leads(self) -> list[Lead]:
        stmt = select(Lead).where(
            Lead.status.notin_(["converted", "lost", "archived"]),
        )
        stmt = self._active_filter(stmt).order_by(Lead.score.desc().nullslast())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
