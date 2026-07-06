"""Client service — lifecycle management, merge, and history."""

from __future__ import annotations

from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.models.client import Client
from backend.repositories import ClientRepository

logger = get_logger("app")


class ClientService:
    def __init__(self, session, client_repository: ClientRepository | None = None):
        self.session = session
        self.repo = client_repository or ClientRepository(session)

    async def create_client(
        self,
        *,
        full_name: str,
        phone: str | None = None,
        email: str | None = None,
        status: str = "active",
        source: str = "manual",
        created_by: UUID | None = None,
        notes: str | None = None,
        **extra,
    ) -> Client:
        if not full_name or not full_name.strip():
            raise ValidationError(message="Client full_name is required")
        if not phone and not email:
            raise ValidationError(
                message="At least one of phone or email is required"
            )

        # Check duplicate by phone
        if phone:
            existing = await self.repo.find_by_phone(phone)
            if existing:
                logger.warning(
                    "duplicate_client_phone",
                    phone=phone,
                    existing_id=str(existing.id),
                )

        client = await self.repo.create(
            full_name=full_name,
            phone=phone,
            email=email,
            status=status,
            source=source,
            created_by=created_by,
            notes=notes,
            **extra,
        )
        logger.info("client_created", client_id=str(client.id), phone=phone)
        return client

    async def update_client(self, client_id: UUID, **kwargs) -> Client:
        client = await self.repo.update(client_id, **kwargs)
        if client is None:
            raise NotFoundError(message=f"Client {client_id} not found")
        logger.info("client_updated", client_id=str(client_id))
        return client

    async def merge_clients(self, primary_id: UUID, secondary_id: UUID) -> Client:
        primary = await self.repo.get(primary_id)
        if primary is None:
            raise NotFoundError(message=f"Primary client {primary_id} not found")
        secondary = await self.repo.get(secondary_id)
        if secondary is None:
            raise NotFoundError(message=f"Secondary client {secondary_id} not found")

        # Merge non-null fields
        for field in ("phone", "email", "full_name", "notes"):
            secondary_val = getattr(secondary, field, None)
            primary_val = getattr(primary, field, None)
            if secondary_val is not None and primary_val is None:
                setattr(primary, field, secondary_val)

        # Reassign related entities to primary
        await self._reassign_entities(secondary_id, primary_id)

        await self.repo.delete(secondary_id)
        logger.info(
            "clients_merged",
            primary_id=str(primary_id),
            secondary_id=str(secondary_id),
        )
        return primary

    async def archive_client(self, client_id: UUID) -> None:
        success = await self.repo.delete(client_id)
        if not success:
            raise NotFoundError(message=f"Client {client_id} not found")
        logger.info("client_archived", client_id=str(client_id))

    async def find_duplicates(self, phone: str | None = None, email: str | None = None) -> list[Client]:
        if phone:
            result = await self.repo.find_by_phone(phone)
            if result:
                return [result]
        if email:
            result = await self.repo.find_by_email(email)
            if result:
                return [result]
        return []

    async def get_client_history(self, client_id: UUID) -> dict:
        client = await self.repo.get(client_id)
        if client is None:
            raise NotFoundError(message=f"Client {client_id} not found")
        return {
            "client": client,
            "communications": client.communications if hasattr(client, "communications") else [],
            "deals": client.deal_participations if hasattr(client, "deal_participations") else [],
            "properties": client.properties if hasattr(client, "properties") else [],
            "documents": client.documents if hasattr(client, "documents") else [],
            "tasks": client.tasks if hasattr(client, "tasks") else [],
        }

    async def _reassign_entities(self, from_id: UUID, to_id: UUID) -> None:
        """Reassign properties, deals, documents from one client to another."""
        from backend.models.property import Property
        from sqlalchemy import update

        await self.session.execute(
            update(Property).where(Property.owner_id == from_id).values(owner_id=to_id)
        )
