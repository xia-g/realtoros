"""Communication service — recording and linking messages."""

from __future__ import annotations

from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.models.communication import Communication
from backend.repositories import CommunicationRepository

logger = get_logger("app")


class CommunicationService:
    def __init__(
        self,
        session,
        communication_repository: CommunicationRepository | None = None,
    ):
        self.session = session
        self.repo = communication_repository or CommunicationRepository(session)

    async def create_communication(
        self,
        *,
        communication_type: str = "note",
        content: str,
        direction: str = "incoming",
        client_id: UUID | None = None,
        deal_id: UUID | None = None,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **extra,
    ) -> Communication:
        if not content or not content.strip():
            raise ValidationError(message="Communication content is required")

        comm = await self.repo.create(
            communication_type=communication_type,
            content=content,
            direction=direction,
            client_id=client_id,
            deal_id=deal_id,
            assigned_to=assigned_to,
            created_by=created_by,
            **extra,
        )
        logger.info(
            "communication_created",
            comm_id=str(comm.id),
            comm_type=communication_type,
            client_id=str(client_id) if client_id else None,
        )
        return comm

    async def link_client(self, comm_id: UUID, client_id: UUID) -> Communication:
        comm = await self.repo.update(comm_id, client_id=client_id)
        if comm is None:
            raise NotFoundError(message=f"Communication {comm_id} not found")
        return comm

    async def link_deal(self, comm_id: UUID, deal_id: UUID) -> Communication:
        comm = await self.repo.update(comm_id, deal_id=deal_id)
        if comm is None:
            raise NotFoundError(message=f"Communication {comm_id} not found")
        return comm

    async def assign_owner(self, comm_id: UUID, user_id: UUID) -> Communication:
        comm = await self.repo.update(comm_id, assigned_to=user_id)
        if comm is None:
            raise NotFoundError(message=f"Communication {comm_id} not found")
        return comm
