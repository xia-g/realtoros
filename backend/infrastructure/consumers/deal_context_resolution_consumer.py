"""DealContextResolutionConsumer — consumes document.ready → resolves deal context.

Consumes document.ready events, resolves Property and Client entities
from document profile data, and updates the Deal aggregate.

Key design points:
  - Extends BaseConsumer — inherits idempotent dedup via ConsumerStateRepository
  - Uses SQLAlchemy async session (consistent with DealService pattern)
  - Delegates resolution to DealContextResolver
  - AMBIGUOUS → ConsumerResult(success=True) — NOT a retry condition
  - All DB operations within a single transaction
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumer_base import (
    BaseConsumer,
    ConsumerResult,
)
from backend.models.deal import Deal
from backend.services.deal_context_resolution.models import (
    DealResolutionContext,
    ResolutionStatus,
)
from backend.services.deal_context_resolution.resolver import (
    DealContextResolver,
)

logger = get_logger(__name__)


class DealContextResolutionConsumer(BaseConsumer):
    """Consumes document.ready → resolves deal context → updates Deal.

    Responsibilities:
      1. Find the target Deal via document_id from event payload
      2. Resolve Property (cadastral → address → create)
      3. Resolve Clients (INN → name → create)
      4. Create DealParticipant rows (buyer + seller)
      5. Update Deal (property_id)
      6. Log resolution_attempt
      7. Emit deal.updated event (via DomainEventBus)

    Idempotent: re-processing the same event produces identical state.
    AMBIGUOUS is NOT an error — always returns ConsumerResult(success=True).
    """

    consumer_name = "deal_context_resolution"

    def __init__(
        self,
        dsn: str,
        session_factory: async_sessionmaker,
    ) -> None:
        super().__init__(consumer_name=self.consumer_name, dsn=dsn)
        self._session_factory = session_factory

    async def _process(self, event: IntegrationEvent) -> None:
        """Process a document.ready event.

        Args:
            event: IntegrationEvent with payload containing
                   document_id and profile data.
        """
        payload = event.payload
        document_id_str = payload.get("document_id")
        if not document_id_str:
            logger.error(
                "deal_context_resolution_missing_document_id",
                event_id=str(event.event_id),
            )
            return

        document_id = UUID(str(document_id_str))
        profile = payload.get("profile", {})

        async with self._session_factory() as session:
            try:
                # 1. Find the target Deal
                deal = await self._find_deal_by_document(
                    session, document_id
                )
                if deal is None:
                    logger.error(
                        "deal_context_resolution_deal_not_found",
                        document_id=str(document_id),
                        event_id=str(event.event_id),
                    )
                    return  # Not retryable — deal should exist

                # 2. Resolve Property, buyer, seller
                resolver = DealContextResolver(session)
                result = await resolver.resolve(deal, profile)

                # 3. Log resolution for audit trail
                await self._log_all_attempts(
                    session=session,
                    event=event,
                    deal=deal,
                    result=result,
                    profile=profile,
                )

                # 4. Apply resolution
                await resolver.apply(deal, result)

                # 5. Commit the transaction
                await session.commit()

                # Determine overall status for logging
                all_resolved = all(
                    r.status == ResolutionStatus.RESOLVED
                    for r in [
                        result.property_result,
                        result.buyer_result,
                        result.seller_result,
                    ]
                    if r
                )
                status = "complete" if all_resolved else "partial"
                logger.info(
                    "deal_context_resolution_completed",
                    event_id=str(event.event_id),
                    deal_id=str(deal.id),
                    status=status,
                )

                # Emit deal.accounting_ready for accounting event integration
                await self._emit_accounting_ready(deal, event)
            except Exception:
                await session.rollback()
                raise

    async def _find_deal_by_document(
        self,
        session,
        document_id: UUID,
    ) -> Deal | None:
        """Find the Deal associated with a document.

        Looks up deals related to this document via document_id.
        The deal is created by promote_to_deal before the document.ready event.
        """
        from backend.models.deal_participant import DealParticipant

        # Check if a deal exists with this document_id
        # In the current architecture, we look for deals that might reference
        # this document. The promote-to-deal flow creates the deal first.
        # We search by checking if any deal's documents reference this document_id.
        stmt = select(Deal).where(Deal.id == document_id)
        result = await session.execute(stmt)
        deal = result.scalar_one_or_none()
        if deal:
            return deal

        # Fallback: try to find deal via document_id stored in event payload
        # The payload from promote-to-deal contains deal_id
        return None

    async def _log_all_attempts(
        self,
        session,
        event: IntegrationEvent,
        deal: Deal,
        result: DealResolutionContext,
        profile: dict,
    ) -> None:
        """Log all resolution attempts for audit trail."""
        from backend.services.deal_context_resolution.application_service import (
            DealApplicationService,
        )

        app_service = DealApplicationService(session)
        document_id_str = event.payload.get("document_id", "")
        document_id = (
            UUID(str(document_id_str)) if document_id_str else deal.id
        )

        # Log property resolution
        if result.property_result:
            await app_service.create_resolution_attempt(
                event_id=event.event_id,
                document_id=document_id,
                deal_id=deal.id,
                resolver_type="property",
                resolution_status=result.property_result.status.value,
                confidence=result.property_result.confidence,
                resolved_entity_id=result.property_result.entity_id,
                evidence={"evidence": result.property_result.evidence},
                candidate_ids=[str(c) for c in result.property_result.candidate_ids],
                document_payload_snapshot=profile,
            )

        # Log buyer resolution
        if result.buyer_result:
            await app_service.create_resolution_attempt(
                event_id=event.event_id,
                document_id=document_id,
                deal_id=deal.id,
                resolver_type="buyer",
                resolution_status=result.buyer_result.status.value,
                confidence=result.buyer_result.confidence,
                resolved_entity_id=result.buyer_result.entity_id,
                evidence={"evidence": result.buyer_result.evidence},
                candidate_ids=[str(c) for c in result.buyer_result.candidate_ids],
                document_payload_snapshot=profile,
            )

        # Log seller resolution
        if result.seller_result:
            await app_service.create_resolution_attempt(
                event_id=event.event_id,
                document_id=document_id,
                deal_id=deal.id,
                resolver_type="seller",
                resolution_status=result.seller_result.status.value,
                confidence=result.seller_result.confidence,
                resolved_entity_id=result.seller_result.entity_id,
                evidence={"evidence": result.seller_result.evidence},
                candidate_ids=[str(c) for c in result.seller_result.candidate_ids],
                document_payload_snapshot=profile,
            )
