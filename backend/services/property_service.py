"""Property service — lifecycle management and document attachment."""

from __future__ import annotations

from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.models.property import Property
from backend.repositories import PropertyRepository

logger = get_logger("app")


class PropertyService:
    def __init__(self, session, property_repository: PropertyRepository | None = None):
        self.session = session
        self.repo = property_repository or PropertyRepository(session)

    async def create_property(
        self,
        *,
        owner_id: UUID | None = None,
        address: str,
        property_type: str = "apartment",
        status: str = "active",
        price: float | None = None,
        area: float | None = None,
        rooms: int | None = None,
        description: str | None = None,
        created_by: UUID | None = None,
        **extra,
    ) -> Property:
        if not address or not address.strip():
            raise ValidationError(message="Property address is required")

        prop = await self.repo.create(
            owner_id=owner_id,
            address=address,
            property_type=property_type,
            status=status,
            price=price,
            area=area,
            rooms=rooms,
            description=description,
            created_by=created_by,
            **extra,
        )
        logger.info("property_created", property_id=str(prop.id), address=address)
        return prop

    async def update_property(self, property_id: UUID, **kwargs) -> Property:
        prop = await self.repo.update(property_id, **kwargs)
        if prop is None:
            raise NotFoundError(message=f"Property {property_id} not found")
        logger.info("property_updated", property_id=str(property_id))
        return prop

    async def assign_owner(self, property_id: UUID, owner_id: UUID) -> Property:
        prop = await self.repo.update(property_id, owner_id=owner_id)
        if prop is None:
            raise NotFoundError(message=f"Property {property_id} not found")
        logger.info("property_owner_assigned", property_id=str(property_id), owner_id=str(owner_id))
        return prop

    async def archive_property(self, property_id: UUID) -> None:
        success = await self.repo.delete(property_id)
        if not success:
            raise NotFoundError(message=f"Property {property_id} not found")
        logger.info("property_archived", property_id=str(property_id))

    async def attach_document(self, property_id: UUID, document_id: UUID) -> Property:
        from backend.models.document import Document
        doc = await self.session.get(Document, document_id)
        if doc is None:
            raise NotFoundError(message=f"Document {document_id} not found")
        doc.property_id = property_id
        await self.session.flush()
        return await self.repo.get(property_id)

    async def detach_document(self, property_id: UUID, document_id: UUID) -> Property:
        from backend.models.document import Document
        doc = await self.session.get(Document, document_id)
        if doc is None:
            raise NotFoundError(message=f"Document {document_id} not found")
        doc.property_id = None
        await self.session.flush()
        return await self.repo.get(property_id)

    async def get_property_history(self, property_id: UUID) -> dict:
        prop = await self.repo.get(property_id)
        if prop is None:
            raise NotFoundError(message=f"Property {property_id} not found")
        return {
            "property": prop,
            "deals": prop.deals if hasattr(prop, "deals") else [],
            "documents": prop.property_documents if hasattr(prop, "property_documents") else [],
            "tasks": prop.property_tasks if hasattr(prop, "property_tasks") else [],
        }
