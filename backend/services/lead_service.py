"""Lead service — lifecycle management, scoring, and conversion.

Every state transition is validated against ADR-0013 status machine,
recorded as a LeadEvent, and logged for audit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from backend.core.domain_events import (
    DomainEvent, get_event_bus,
    EVENT_LEAD_CONVERTED, EVENT_LEAD_MERGED,
)
from backend.core.exceptions import (
    DuplicateEntityError,
    LeadStateError,
    NotFoundError,
    ValidationError,
)
from backend.core.logging import get_logger
from backend.core.audit import get_audit_context
from backend.models.lead import Lead
from backend.models.lead_event import LeadEvent
from backend.repositories import LeadRepository
from backend.repositories.client_repository import ClientRepository
from backend.services.client_service import ClientService

logger = get_logger("lead")

# ── ADR-0013 valid status transitions ──
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"contact_made", "lost", "spam"},
    "contact_made": {"qualifying", "lost", "spam"},
    "qualifying": {"qualified", "lost", "spam"},
    "qualified": {"converted", "lost", "qualifying", "spam"},
    "converted": set(),
    "lost": {"qualifying", "qualified"},
    "archived": set(),
}


class ConversionResult:
    """Result of a lead-to-client conversion."""

    def __init__(
        self,
        lead: Lead,
        client,
        deal=None,
        event: LeadEvent | None = None,
    ) -> None:
        self.lead = lead
        self.client = client
        self.deal = deal
        self.event = event


class LeadService:
    def __init__(
        self,
        session,
        lead_repository: LeadRepository | None = None,
        client_repository: ClientRepository | None = None,
    ) -> None:
        self.session = session
        self.lead_repo = lead_repository or LeadRepository(session)
        self.client_repo = client_repository or ClientRepository(session)
        self.client_service = ClientService(
            session, client_repository=self.client_repo
        )

    async def create_lead(
        self,
        source: str,
        *,
        source_id: str | None = None,
        source_metadata: dict | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        telegram_id: str | None = None,
        interest_type: str = "unknown",
        budget_min: float | None = None,
        budget_max: float | None = None,
        property_type: str | None = None,
        created_by: UUID | None = None,
        **extra,
    ) -> Lead:
        # Check for duplicate by source
        if source_id:
            existing = await self.lead_repo.find_by_source(source, source_id)
            if existing and existing.deleted_at is None:
                raise DuplicateEntityError(
                    message=f"Lead from {source}/{source_id} already exists",
                    details={"lead_id": str(existing.id)},
                )

        # Check for duplicate by phone
        if phone:
            dupes = await self.lead_repo.find_by_phone(phone)
            for dupe in dupes:
                if dupe.status not in ("converted", "lost"):
                    logger.warning(
                        "duplicate_lead_detected",
                        phone=phone,
                        existing_id=str(dupe.id),
                    )

        lead = await self.lead_repo.create(
            source=source,
            source_id=source_id,
            source_metadata=source_metadata or {},
            full_name=full_name,
            phone=phone,
            email=email,
            telegram_id=telegram_id,
            interest_type=interest_type,
            budget_min=budget_min,
            budget_max=budget_max,
            property_type=property_type,
            created_by=created_by,
            status="new",
            priority="cold",
            score=0.0,
            **extra,
        )

        # Record creation event
        await self._record_event(lead, "lead_created")
        logger.info(
            "lead_created",
            lead_id=str(lead.id),
            source=source,
            phone=phone,
        )
        return lead

    async def assign_lead(
        self, lead_id: UUID, user_id: UUID, assigned_by: UUID | None = None
    ) -> Lead:
        lead = await self.lead_repo.get(lead_id)
        if lead is None:
            raise NotFoundError(message=f"Lead {lead_id} not found")

        old_assignee = lead.assigned_to
        lead.assigned_to = user_id
        lead.assigned_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._record_event(
            lead,
            "lead_assigned",
            metadata={
                "from_user_id": str(old_assignee) if old_assignee else None,
                "to_user_id": str(user_id),
            },
        )
        logger.info(
            "lead_assigned",
            lead_id=str(lead_id),
            user_id=str(user_id),
        )
        return lead

    async def change_status(
        self, lead_id: UUID, new_status: str, reason: str | None = None
    ) -> Lead:
        lead = await self.lead_repo.get(lead_id)
        if lead is None:
            raise NotFoundError(message=f"Lead {lead_id} not found")

        if new_status == lead.status:
            return lead

        allowed = _ALLOWED_TRANSITIONS.get(lead.status, set())
        if new_status not in allowed:
            raise LeadStateError(
                message=f"Cannot transition from {lead.status} to {new_status}",
                details={
                    "current": lead.status,
                    "target": new_status,
                    "allowed": list(allowed),
                },
            )

        old_status = lead.status
        lead.previous_status = old_status
        lead.status = new_status
        lead.status_changed_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._record_event(
            lead,
            "status_changed",
            metadata={
                "from_status": old_status,
                "to_status": new_status,
                "reason": reason,
            },
        )
        logger.info(
            "lead_status_changed",
            lead_id=str(lead_id),
            from_status=old_status,
            to_status=new_status,
        )
        return lead

    async def score_lead(
        self, lead_id: UUID, score: float, version: str = "v1", metadata: dict | None = None
    ) -> Lead:
        if not 0.0 <= score <= 1.0:
            raise ValidationError(
                message="Score must be between 0.0 and 1.0",
                details={"score": score},
            )

        lead = await self.lead_repo.get(lead_id)
        if lead is None:
            raise NotFoundError(message=f"Lead {lead_id} not found")

        old_score = lead.score
        lead.score = score
        lead.score_version = version
        lead.score_components = metadata or {}
        lead.last_scored_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._record_event(
            lead,
            "score_changed",
            metadata={
                "from_score": old_score,
                "to_score": score,
                "version": version,
            },
        )
        logger.info(
            "lead_scored",
            lead_id=str(lead_id),
            score=score,
            version=version,
        )
        return lead

    async def qualify_lead(
        self,
        lead_id: UUID,
        qualified_by: UUID,
        note: str | None = None,
        priority: str = "warm",
    ) -> Lead:
        lead = await self.change_status(lead_id, "qualified")

        lead.qualified_by = qualified_by
        lead.qualified_at = datetime.now(timezone.utc)
        lead.qualification_note = note
        lead.priority = priority
        await self.session.flush()

        await self._record_event(
            lead,
            "lead_qualified",
            metadata={
                "qualified_by": str(qualified_by),
                "priority": priority,
            },
        )
        logger.info(
            "lead_qualified",
            lead_id=str(lead_id),
            priority=priority,
        )
        return lead

    async def merge_leads(
        self, primary_id: UUID, secondary_id: UUID, merged_by: UUID | None = None
    ) -> Lead:
        primary = await self.lead_repo.get(primary_id)
        if primary is None:
            raise NotFoundError(message=f"Primary lead {primary_id} not found")
        secondary = await self.lead_repo.get(secondary_id)
        if secondary is None:
            raise NotFoundError(message=f"Secondary lead {secondary_id} not found")

        # Merge fields: prefer non-null values from secondary
        for field in ("phone", "email", "telegram_id", "full_name", "budget_min", "budget_max", "property_type"):
            secondary_val = getattr(secondary, field, None)
            primary_val = getattr(primary, field, None)
            if secondary_val is not None and primary_val is None:
                setattr(primary, field, secondary_val)

        # Soft-delete the secondary lead
        secondary.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._record_event(
            primary,
            "lead_merged",
            metadata={
                "merged_lead_id": str(secondary_id),
                "merged_by": str(merged_by) if merged_by else None,
            },
        )
        logger.info(
            "leads_merged",
            primary_id=str(primary_id),
            secondary_id=str(secondary_id),
        )

        bus = get_event_bus()
        await bus.emit(DomainEvent(
            event_type=EVENT_LEAD_MERGED,
            entity_type="lead",
            entity_id=primary_id,
            correlation_id=str(uuid4()),
            actor_id=str(merged_by) if merged_by else "system",
            payload={"secondary_id": str(secondary_id), "merged_by": str(merged_by) if merged_by else "system"},
        ))
        return primary

    async def archive_lead(self, lead_id: UUID) -> None:
        success = await self.lead_repo.delete(lead_id)
        if not success:
            raise NotFoundError(message=f"Lead {lead_id} not found")
        logger.info("lead_archived", lead_id=str(lead_id))

    async def convert_lead(
        self,
        lead_id: UUID,
        *,
        converted_by: UUID,
        create_deal: bool = False,
        deal_type: str | None = None,
        **client_fields,
    ) -> ConversionResult:
        """Complete lead→client conversion in a single transaction.

        1. Fetch and validate lead
        2. Create Client
        3. Update Lead to 'converted'
        4. Record LeadEvent
        5. Optionally create Deal
        """
        lead = await self.lead_repo.get(lead_id)
        if lead is None:
            raise NotFoundError(message=f"Lead {lead_id} not found")

        if lead.status != "qualified":
            raise LeadStateError(
                message="Only qualified leads can be converted",
                details={"current_status": lead.status},
            )

        # ── Step 1: Create Client ──
        client_data = {
            "full_name": client_fields.get("full_name") or lead.full_name,
            "phone": client_fields.get("phone") or lead.phone,
            "email": client_fields.get("email") or lead.email,
            "status": "active",
            "source": "lead_conversion",
            "created_by": converted_by,
            "notes": client_fields.get("notes") or f"Converted from lead {lead_id}",
        }
        client = await self.client_service.create_client(**client_data)

        # ── Step 2: Update Lead ──
        lead.status = "converted"
        lead.previous_status = "qualified"
        lead.status_changed_at = datetime.now(timezone.utc)
        lead.client_id = client.id
        lead.converted_at = datetime.now(timezone.utc)
        await self.session.flush()

        # ── Step 3: Record conversion event ──
        event = await self._record_event(
            lead,
            "lead_converted",
            metadata={
                "client_id": str(client.id),
                "converted_by": str(converted_by),
            },
        )

        # ── Step 4: Optional deal creation ──
        deal = None
        if create_deal:
            from backend.services.deal_service import DealService
            deal_svc = DealService(self.session)
            deal = await deal_svc.create_deal(
                property_id=None,
                deal_type=deal_type or lead.interest_type,
                created_by=converted_by,
                participants=[client.id],
            )

        logger.info(
            "lead_converted",
            lead_id=str(lead_id),
            client_id=str(client.id),
            deal_id=str(deal.id) if deal else None,
        )

        bus = get_event_bus()
        await bus.emit(DomainEvent(
            event_type=EVENT_LEAD_CONVERTED,
            entity_type="lead",
            entity_id=lead_id,
            correlation_id=str(uuid4()),
            actor_id=str(converted_by),
            payload={"client_id": str(client.id), "deal_id": str(deal.id) if deal else None},
        ))
        return ConversionResult(lead=lead, client=client, deal=deal, event=event)

    async def _record_event(
        self,
        lead: Lead,
        event_type: str,
        metadata: dict | None = None,
    ) -> LeadEvent:
        """Record a lead lifecycle event."""
        event = LeadEvent(
            lead_id=lead.id,
            event_type=event_type,
            from_status=lead.previous_status,
            to_status=lead.status,
            from_score=lead.score,
            change_reason=metadata.get("reason") if metadata else None,
            metadata=metadata or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event
