from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.domain_events import (
    DomainEvent, get_event_bus,
    EVENT_CLIENT_CREATED, EVENT_CLIENT_UPDATED, EVENT_CLIENT_DELETED,
)
from backend.repositories.client import ClientRepository
from backend.services.base import BaseService


class ClientService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = ClientRepository(session)
        self._event_bus = None

    def _get_event_bus(self):
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    @property
    def repo(self) -> ClientRepository:
        return self._repo

    async def _emit(self, event_type: str, entity_id: UUID, **extra):
        bus = self._get_event_bus()
        await bus.emit(DomainEvent(
            event_type=event_type,
            entity_type="client",
            entity_id=entity_id,
            correlation_id=str(uuid4()),
            actor_id=extra.pop("actor_id", "system"),
        ))

    async def create(self, **kwargs):
        obj = await super().create(**kwargs)
        await self._emit(EVENT_CLIENT_CREATED, obj.id, **kwargs)
        return obj

    async def update(self, id: UUID, **kwargs):
        obj = await super().update(id, **kwargs)
        if obj:
            await self._emit(EVENT_CLIENT_UPDATED, id, **kwargs)
        return obj

    async def delete(self, id: UUID) -> bool:
        result = await super().delete(id)
        if result:
            await self._emit(EVENT_CLIENT_DELETED, id)
        return result

    async def search_by_phone(self, phone: str):
        items, _ = await self.repo.list(filters={"phone": phone})
        return items

    async def search_by_telegram(self, telegram_id: str):
        items, _ = await self.repo.list(filters={"telegram_id": telegram_id})
        return items