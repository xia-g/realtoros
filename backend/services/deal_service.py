"""Deal service — lifecycle management, participants, and status machine."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.models.deal import Deal
from backend.models.deal_participant import DealParticipant
from backend.repositories import DealRepository

logger = get_logger("app")

_ALLOWED_DEAL_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "negotiation": {"offer_made", "cancelled"},
    "offer_made": {"under_review", "cancelled"},
    "under_review": {"approved", "cancelled"},
    "approved": {"closed", "cancelled"},
    "closed": set(),
    "cancelled": set(),
}


class DealService:
    def __init__(self, session, deal_repository: DealRepository | None = None):
        self.session = session
        self.repo = deal_repository or DealRepository(session)

    async def create_deal(
        self,
        *,
        property_id: UUID | None = None,
        deal_type: str = "buy",
        status: str = "negotiation",
        created_by: UUID | None = None,
        participants: list[UUID] | None = None,
        **extra,
    ) -> Deal:
        if not participants:
            raise ValidationError(message="At least one participant is required")

        deal = await self.repo.create(
            property_id=property_id,
            deal_type=deal_type,
            status=status,
            created_by=created_by,
            **extra,
        )

        # Add participants
        for client_id in participants:
            participant = DealParticipant(
                deal_id=deal.id,
                client_id=client_id,
                role="buyer" if deal_type in ("buy", "rent_long") else "seller",
            )
            self.session.add(participant)

        await self.session.flush()
        logger.info(
            "deal_created",
            deal_id=str(deal.id),
            deal_type=deal_type,
            participants=len(participants),
        )
        return deal

    async def change_status(self, deal_id: UUID, new_status: str) -> Deal:
        deal = await self.repo.get(deal_id)
        if deal is None:
            raise NotFoundError(message=f"Deal {deal_id} not found")

        if new_status == deal.status:
            return deal

        allowed = _ALLOWED_DEAL_STATUS_TRANSITIONS.get(deal.status, set())
        if new_status not in allowed:
            raise ValidationError(
                message=f"Cannot transition deal from {deal.status} to {new_status}",
                details={"current": deal.status, "target": new_status},
            )

        deal.status = new_status
        await self.session.flush()
        logger.info(
            "deal_status_changed",
            deal_id=str(deal_id),
            to_status=new_status,
        )
        return deal

    async def attach_property(self, deal_id: UUID, property_id: UUID) -> Deal:
        deal = await self.repo.update(deal_id, property_id=property_id)
        if deal is None:
            raise NotFoundError(message=f"Deal {deal_id} not found")
        logger.info("deal_property_attached", deal_id=str(deal_id), property_id=str(property_id))
        return deal

    async def add_participant(self, deal_id: UUID, client_id: UUID, role: str = "buyer") -> DealParticipant:
        deal = await self.repo.get(deal_id)
        if deal is None:
            raise NotFoundError(message=f"Deal {deal_id} not found")
        participant = DealParticipant(deal_id=deal_id, client_id=client_id, role=role)
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def remove_participant(self, deal_id: UUID, client_id: UUID) -> None:
        from sqlalchemy import select
        stmt = select(DealParticipant).where(
            DealParticipant.deal_id == deal_id,
            DealParticipant.client_id == client_id,
        )
        result = await self.session.execute(stmt)
        participant = result.scalar_one_or_none()
        if participant is None:
            raise NotFoundError(
                message=f"Client {client_id} is not a participant in deal {deal_id}"
            )
        await self.session.delete(participant)
        await self.session.flush()

    async def close_deal(self, deal_id: UUID) -> Deal:
        return await self.change_status(deal_id, "closed")

    async def cancel_deal(self, deal_id: UUID) -> Deal:
        return await self.change_status(deal_id, "cancelled")
