"""
Knowledge Events — immutable domain events for the knowledge layer.

All events are append-only. NO mutation.
Future Knowledge Projection (v2.1) will rebuild from this event log.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventVersion(str, Enum):
    V1_0 = "1.0"    # initial extraction
    V1_1 = "1.1"    # with trust + authority
    V2_0 = "2.0"    # with merge + conflict


class KnowledgeEventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_MATCHED = "entity_matched"
    ENTITY_MERGED = "entity_merged"
    ALIAS_ADDED = "alias_added"
    PROPERTY_MATCHED = "property_matched"
    AGREEMENT_MATCHED = "agreement_matched"
    CONFIDENCE_UPDATED = "confidence_updated"
    TRUST_UPDATED = "trust_updated"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    KNOWLEDGE_SUPERSEDED = "knowledge_superseded"


@dataclass(frozen=True)
class KnowledgeEvent:
    """Base domain event. Immutable."""
    event_type: KnowledgeEventType
    entity_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    caused_by_revision: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = field(default_factory=dict)
    event_version: str = EventVersion.V1_0.value

    @property
    def event_id(self) -> str:
        return self.id

    def to_dict(self) -> dict:
        return {
            "event_id": self.id,
            "event_type": self.event_type.value,
            "entity_id": self.entity_id,
            "document_id": self.document_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "event_version": self.event_version,
        }


# ── Factory Functions ──

def entity_created(entity_id: str, doc_id: str, payload: dict | None = None) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.ENTITY_CREATED,
        entity_id=entity_id, document_id=doc_id,
        payload=payload or {},
    )

def entity_matched(entity_id: str, doc_id: str, existing_name: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.ENTITY_MATCHED,
        entity_id=entity_id, document_id=doc_id,
        payload={"matched_existing": existing_name},
    )

def entity_merged(survivor_id: str, absorbed_id: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.ENTITY_MERGED,
        entity_id=survivor_id, document_id=doc_id,
        payload={"absorbed_entity_id": absorbed_id},
    )

def alias_added(entity_id: str, original: str, normalized: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.ALIAS_ADDED,
        entity_id=entity_id, document_id=doc_id,
        payload={"original": original, "normalized": normalized},
    )

def property_matched(entity_id: str, cadastral: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.PROPERTY_MATCHED,
        entity_id=entity_id, document_id=doc_id,
        payload={"cadastral_number": cadastral},
    )

def agreement_matched(entity_id: str, number: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.AGREEMENT_MATCHED,
        entity_id=entity_id, document_id=doc_id,
        payload={"agreement_number": number},
    )

def confidence_updated(entity_id: str, old_conf: float, new_conf: float, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.CONFIDENCE_UPDATED,
        entity_id=entity_id, document_id=doc_id,
        payload={"old_confidence": old_conf, "new_confidence": new_conf},
    )

def trust_updated(entity_id: str, old_level: str, new_level: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.TRUST_UPDATED,
        entity_id=entity_id, document_id=doc_id,
        payload={"old_trust": old_level, "new_trust": new_level},
    )

def conflict_detected(entity_id: str, field: str, values: list, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.CONFLICT_DETECTED,
        entity_id=entity_id, document_id=doc_id,
        payload={"field": field, "conflicting_values": values},
    )

def conflict_resolved(entity_id: str, field: str, chosen: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.CONFLICT_RESOLVED,
        entity_id=entity_id, document_id=doc_id,
        payload={"field": field, "resolved_to": chosen},
    )

def knowledge_superseded(entity_id: str, superseded_by: str, reason: str, doc_id: str) -> KnowledgeEvent:
    return KnowledgeEvent(
        event_type=KnowledgeEventType.KNOWLEDGE_SUPERSEDED,
        entity_id=entity_id, document_id=doc_id,
        payload={"superseded_by": superseded_by, "reason": reason},
    )
