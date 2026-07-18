"""
KnowledgeEvolutionService — registers knowledge events.

Tracks: entity creation, matching, merging, trust, conflicts.
NO writes to Knowledge Store. Events only. Append-only.

Future v2.1 Knowledge Projection rebuilds from this event log.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.knowledge_events import (
    KnowledgeEvent,
    entity_created, entity_matched, alias_added,
    property_matched, agreement_matched,
    confidence_updated, trust_updated,
    conflict_detected, conflict_resolved,
)
from domain.business_relationship.trust import TrustScore, TrustLevel
from domain.business_relationship.authority import AuthorityResolver, AuthorityLevel
from domain.business_relationship.conflict import (
    KnowledgeConflict, ConflictDetector, ConflictStatus,
)
from domain.business_relationship.support_models import ConfidenceHistory


@dataclass
class KnowledgeEvolutionResult:
    """Результат эволюции знаний: события + конфликты + trust."""
    events: list[KnowledgeEvent] = field(default_factory=list)
    conflicts: list[KnowledgeConflict] = field(default_factory=list)
    trust_scores: dict[str, TrustScore] = field(default_factory=dict)
    authority_summary: dict[str, str] = field(default_factory=dict)


@dataclass
class KnowledgeExplanation:
    """Объяснение происхождения знания."""
    entity_id: str
    current_value: str
    chosen_because: str
    supporting_events: list[KnowledgeEvent] = field(default_factory=list)
    supporting_documents: list[str] = field(default_factory=list)
    authority_level: str = ""
    trust_level: str = ""


class KnowledgeEvolutionService:
    """Регистрирует события эволюции знаний. Append-only."""

    def __init__(
        self,
        authority: AuthorityResolver | None = None,
    ):
        self._authority = authority or AuthorityResolver()
        self._event_log: list[KnowledgeEvent] = []
        self._trust_store: dict[str, TrustScore] = {}
        self._conflicts: list[KnowledgeConflict] = []
        self._explanations: dict[str, list[KnowledgeExplanation]] = {}

    # ── Entity events ──

    def on_entity_created(self, entity_id: str, document_id: str,
                          display_name: str = "") -> KnowledgeEvent:
        ev = entity_created(entity_id, document_id, {"display_name": display_name})
        self._event_log.append(ev)
        self._trust_store[entity_id] = TrustScore(entity_id=entity_id)
        return ev

    def on_entity_matched(self, entity_id: str, document_id: str,
                          matched_name: str, document_role: str = "") -> KnowledgeEvent:
        ev = entity_matched(entity_id, document_id, matched_name)
        ev = KnowledgeEvent(
            event_type=ev.event_type, entity_id=entity_id, document_id=document_id,
            payload={**ev.payload, "document_role": document_role},
            id=ev.id, timestamp=ev.timestamp,
        )
        self._event_log.append(ev)
        # Update trust
        ts = self._trust_store.get(entity_id)
        if ts:
            is_official = self._authority.resolve(document_role) in (
                AuthorityLevel.OFFICIAL, AuthorityLevel.HIGH)
            ts.add_evidence(document_id, is_official=is_official)
        return ev

    def on_alias_added(self, entity_id: str, original: str, normalized: str,
                       document_id: str) -> KnowledgeEvent:
        ev = alias_added(entity_id, original, normalized, document_id)
        self._event_log.append(ev)
        return ev

    def on_property_matched(self, entity_id: str, cadastral: str,
                            document_id: str) -> KnowledgeEvent:
        ev = property_matched(entity_id, cadastral, document_id)
        self._event_log.append(ev)
        ts = self._trust_store.get(entity_id)
        if ts:
            ts.add_evidence(document_id)
        return ev

    def on_agreement_matched(self, entity_id: str, number: str,
                             document_id: str) -> KnowledgeEvent:
        ev = agreement_matched(entity_id, number, document_id)
        self._event_log.append(ev)
        return ev

    def on_confidence_updated(self, entity_id: str, old_conf: float,
                              new_conf: float, document_id: str) -> KnowledgeEvent:
        ev = confidence_updated(entity_id, old_conf, new_conf, document_id)
        self._event_log.append(ev)
        return ev

    def on_trust_updated(self, entity_id: str, old_level: str,
                         new_level: str, document_id: str) -> KnowledgeEvent:
        ev = trust_updated(entity_id, old_level, new_level, document_id)
        self._event_log.append(ev)
        return ev

    # ── Conflict tracking ──

    def check_conflict(self, entity_id: str, field: str,
                       old_value: str | None, new_value: str,
                       document_id: str, authority_level: str = "normal") -> KnowledgeConflict | None:
        conflict = ConflictDetector.detect(entity_id, field, old_value, new_value, authority_level)
        if conflict:
            self._conflicts.append(conflict)
            ev = conflict_detected(entity_id, field, 
                                   [c.value for c in conflict.candidates], document_id)
            self._event_log.append(ev)
        return conflict

    # ── Queries ──

    def get_events(self, entity_id: str | None = None) -> list[KnowledgeEvent]:
        if entity_id:
            return [e for e in self._event_log if e.entity_id == entity_id]
        return list(self._event_log)

    def get_timeline(self, entity_id: str) -> list[dict]:
        """Хронология событий для сущности."""
        events = sorted(
            [e for e in self._event_log if e.entity_id == entity_id],
            key=lambda e: e.timestamp
        )
        return [e.to_dict() for e in events]

    def get_conflicts(self, status: ConflictStatus | None = None) -> list[KnowledgeConflict]:
        if status:
            return [c for c in self._conflicts if c.status == status]
        return list(self._conflicts)

    def get_trust(self, entity_id: str) -> TrustScore | None:
        return self._trust_store.get(entity_id)

    def get_explanation(self, entity_id: str) -> KnowledgeExplanation | None:
        """Объяснить происхождение знания о сущности."""
        events = self.get_events(entity_id)
        trust = self._trust_store.get(entity_id)
        return KnowledgeExplanation(
            entity_id=entity_id,
            current_value="",  # would be filled from canonical
            chosen_because=" и ".join(e.event_type.value for e in events),
            supporting_events=events,
            supporting_documents=list(set(e.document_id for e in events if e.document_id)),
            authority_level=self._authority.resolve("sale_contract").value,
            trust_level=trust.current_level.value if trust else "unknown",
        )

    # ── Result ──

    def result(self) -> KnowledgeEvolutionResult:
        return KnowledgeEvolutionResult(
            events=list(self._event_log),
            conflicts=list(self._conflicts),
            trust_scores=dict(self._trust_store),
            authority_summary={
                e.entity_id: self._authority.resolve("sale_contract").value
                for e in self._event_log if e.entity_id
            },
        )
