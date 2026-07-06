from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.domain_events import (
    DomainEvent, get_event_bus,
    EVENT_DEAL_CREATED, EVENT_DEAL_UPDATED, EVENT_DEAL_DELETED,
)
from backend.models import Deal, DealParticipant
from backend.repositories.deal import DealRepository
from backend.services.base import BaseService


class DealService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = DealRepository(session)
        self._event_bus = None

    def _get_event_bus(self):
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    @property
    def repo(self) -> DealRepository:
        return self._repo

    async def _emit(self, event_type: str, entity_id: UUID, **extra):
        bus = self._get_event_bus()
        await bus.emit(DomainEvent(
            event_type=event_type,
            entity_type="deal",
            entity_id=entity_id,
            correlation_id=str(uuid4()),
            actor_id=extra.pop("actor_id", "system"),
        ))

    async def create(self, **kwargs):
        obj = await super().create(**kwargs)
        await self._emit(EVENT_DEAL_CREATED, obj.id, **kwargs)
        return obj

    async def update(self, id: UUID, **kwargs):
        obj = await super().update(id, **kwargs)
        if obj:
            await self._emit(EVENT_DEAL_UPDATED, id, **kwargs)
        return obj

    async def delete(self, id: UUID) -> bool:
        result = await super().delete(id)
        if result:
            await self._emit(EVENT_DEAL_DELETED, id)
        return result

    async def get_with_participants(self, deal_id):
        stmt = (
            select(Deal)
            .where(Deal.id == deal_id)
            .options(selectinload(Deal.participants))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_client(self, client_id):
        stmt = (
            select(Deal)
            .join(DealParticipant)
            .where(DealParticipant.client_id == client_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())