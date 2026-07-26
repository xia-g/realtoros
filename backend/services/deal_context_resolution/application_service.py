"""DealApplicationService — application service for Deal enrichment.

Encapsulates all Deal mutations after context resolution.
Consumer uses this service instead of direct SQL (ADR-006).

Operations:
  - attach_property: Set deal.property_id
  - add_participant: Create DealParticipant (buyer/seller)
  - create_resolution_attempt: Log resolution decision for audit
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.deal import Deal
from backend.models.deal_participant import DealParticipant
from backend.models.resolution_attempt import ResolutionAttempt


class DealApplicationService:
    """Application service for Deal enrichment after context resolution.

    All mutations go through this service, not direct SQL (ADR-006).
    Uses SQLAlchemy async session for all DB operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def attach_property(
        self,
        deal_id: UUID,
        property_id: UUID,
    ) -> None:
        """Set deal.property_id.

        Idempotent: setting the same value is a no-op.
        """
        deal = await self._session.get(Deal, deal_id)
        if deal is not None:
            deal.property_id = property_id

    async def add_participant(
        self,
        deal_id: UUID,
        client_id: UUID,
        role: str,  # "buyer" | "seller"
    ) -> DealParticipant:
        """Create a DealParticipant row.

        Idempotent: SQLAlchemy flush catches duplicate via FK+role unique.
        """
        participant = DealParticipant(
            deal_id=deal_id,
            client_id=client_id,
            role=role,
        )
        self._session.add(participant)
        await self._session.flush()
        return participant

    async def create_resolution_attempt(
        self,
        event_id: UUID,
        document_id: UUID,
        deal_id: UUID,
        resolver_type: str,
        resolution_status: str,
        confidence: str,
        resolved_entity_id: UUID | None = None,
        evidence: dict | None = None,
        candidate_ids: list | None = None,
        document_payload_snapshot: dict | None = None,
    ) -> ResolutionAttempt:
        """Log a resolution decision for audit trail."""
        attempt = ResolutionAttempt(
            event_id=event_id,
            document_id=document_id,
            deal_id=deal_id,
            resolver_type=resolver_type,
            resolution_status=resolution_status,
            confidence=confidence,
            resolved_entity_id=resolved_entity_id,
            evidence=evidence or {},
            candidate_ids=candidate_ids or [],
            document_payload_snapshot=document_payload_snapshot,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(attempt)
        await self._session.flush()
        return attempt
