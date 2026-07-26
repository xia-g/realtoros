"""IntegrationEvent — durable event envelope for the Event Backbone.

Stream 3. Frozen dataclass, passes through Outbox → Publisher → Consumer.
NOT a replacement for DomainEvent — this is the durable delivery layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from backend.core.domain_events import DomainEvent


@dataclass(frozen=True)
class IntegrationEvent:
    """Durable event envelope.

    Immutable once created. event_id is stable across retries.
    aggregate_id is the stable business entity ID.
    No entity_id field — use aggregate_type + aggregate_id.
    """

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    version: int = 1
    payload: dict = field(default_factory=dict)
    metadata: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON/JSONB storage."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at.isoformat(),
            "version": self.version,
            "payload": self.payload,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrationEvent:
        """Deserialize from dict."""
        occurred_at = data.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)

        return cls(
            event_id=UUID(data["event_id"]),
            event_type=data["event_type"],
            aggregate_type=data["aggregate_type"],
            aggregate_id=data["aggregate_id"],
            occurred_at=occurred_at,
            version=data.get("version", 1),
            payload=data.get("payload", {}),
            metadata=data.get("metadata"),
        )


class EventAdapter:
    """Converts DomainEvent → IntegrationEvent.

    This is the bridge between the in-memory DomainEventBus
    and the durable Event Backbone.
    """

    @staticmethod
    def to_integration(
        domain_event: DomainEvent,
        aggregate_type: str | None = None,
        metadata: dict | None = None,
    ) -> IntegrationEvent:
        """Convert a DomainEvent to an IntegrationEvent.

        Args:
            domain_event: The source domain event.
            aggregate_type: Override for aggregate type (defaults from entity_type).
            metadata: Additional metadata (schema_version, producer, correlation_id).

        Returns:
            A new frozen IntegrationEvent.
        """
        # Map entity_type to aggregate_type
        if aggregate_type is None:
            aggregate_type = domain_event.entity_type.capitalize()

        # Use domain_event.entity_id as aggregate_id (stable business ID)
        # Note: DomainEvent.entity_id is used as aggregate_id
        aggregate_id = str(domain_event.entity_id)

        # Build metadata
        event_metadata = dict(metadata or {})
        if "schema_version" not in event_metadata:
            event_metadata["schema_version"] = 1
        if "producer" not in event_metadata:
            event_metadata["producer"] = "domain"
        if domain_event.correlation_id:
            event_metadata["correlation_id"] = domain_event.correlation_id

        return IntegrationEvent(
            event_id=uuid4(),
            event_type=domain_event.event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            occurred_at=domain_event.occurred_at,
            version=1,
            payload=domain_event.payload,
            metadata=event_metadata,
        )
