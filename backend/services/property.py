from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.domain_events import (
    DomainEvent, get_event_bus,
    EVENT_PROPERTY_CREATED, EVENT_PROPERTY_UPDATED, EVENT_PROPERTY_DELETED,
)
from backend.repositories.property import PropertyRepository
from backend.services.base import BaseService


class PropertyService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._repo = PropertyRepository(session)
        self._event_bus = None

    def _get_event_bus(self):
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    @property
    def repo(self) -> PropertyRepository:
        return self._repo

    async def _emit(self, event_type: str, entity_id: UUID, **extra):
        bus = self._get_event_bus()
        await bus.emit(DomainEvent(
            event_type=event_type,
            entity_type="property",
            entity_id=entity_id,
            correlation_id=str(uuid4()),
            actor_id=extra.pop("actor_id", "system"),
        ))

    async def create(self, **kwargs):
        obj = await super().create(**kwargs)
        await self._emit(EVENT_PROPERTY_CREATED, obj.id, **kwargs)
        return obj

    async def update(self, id: UUID, **kwargs):
        obj = await super().update(id, **kwargs)
        if obj:
            await self._emit(EVENT_PROPERTY_UPDATED, id, **kwargs)
        return obj

    async def delete(self, id: UUID) -> bool:
        result = await super().delete(id)
        if result:
            await self._emit(EVENT_PROPERTY_DELETED, id)
        return result

    async def get_by_owner(self, owner_id):
        items, _ = await self.repo.list(filters={"owner_id": owner_id})
        return items

    async def get_available(self):
        items, _ = await self.repo.list(filters={"status": "available"})
        return items