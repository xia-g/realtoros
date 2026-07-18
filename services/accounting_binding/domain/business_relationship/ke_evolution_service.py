"""
KnowledgeEvolutionService — coordinator of knowledge evolution computation.

Stateless. Deterministic. Side-effect free.
NO mutation of Aggregates. NO IO. NO DB.
"""
from __future__ import annotations

from datetime import datetime

from domain.business_relationship.ke_identifiers import KnowledgeEventId
from domain.business_relationship.ke_enums import (
    KnowledgeEventType, TrustLevel, AuthorityLevel,
)
from domain.business_relationship.ke_event import KnowledgeEvent
from domain.business_relationship.ke_change import KnowledgeChange
from domain.business_relationship.ke_delta import KnowledgeDelta
from domain.business_relationship.ke_conflict import KnowledgeConflict
from domain.business_relationship.ke_result import (
    KnowledgeEvolutionResult, KnowledgeEvolutionReport,
)
from domain.business_relationship.ke_conflict_detector import ConflictDetector
from domain.business_relationship.ke_trust_evaluator import TrustEvaluator
from domain.business_relationship.ke_authority_evaluator import AuthorityEvaluator
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType


class KnowledgeEvolutionService:
    """Оркестратор вычисления эволюции знаний.

    Pipeline:
      CanonicalEntity + Facts + Agreement
        → KnowledgeEvent → KnowledgeDelta
        → ConflictDetector → TrustEvaluator → AuthorityEvaluator
        → KnowledgeEvolutionResult
    """

    def __init__(self):
        self._conflict_detector = ConflictDetector()
        self._trust_evaluator = TrustEvaluator()
        self._authority_evaluator = AuthorityEvaluator()

    def evolve(
        self,
        entity: CanonicalEntity,
        facts: list[BusinessFact],
        agreement: Agreement | None = None,
    ) -> KnowledgeEvolutionResult:
        """Compute knowledge evolution for a canonical entity.

        Stateless. Deterministic. Same inputs → same result.
        """
        events: list[KnowledgeEvent] = []
        deltas: list[KnowledgeDelta] = []
        all_conflicts: list[KnowledgeConflict] = []

        now = datetime.utcnow()

        # 1. Build event
        event = self._build_event(entity, facts, agreement, now)
        events.append(event)

        # 2. Build delta
        delta = self._build_delta(entity, facts, event)
        deltas.append(delta)

        # 3. Detect conflicts
        conflicts = self._conflict_detector.detect(delta)
        all_conflicts.extend(conflicts)

        # 4. Evaluate trust
        trust = self._trust_evaluator.evaluate(event)

        # 5. Evaluate authority
        authority = self._authority_evaluator.evaluate(event)

        return KnowledgeEvolutionResult(
            events=tuple(events),
            deltas=tuple(deltas),
            conflicts=tuple(all_conflicts),
            trust_level=trust,
            authority_level=authority,
        )

    def _build_event(
        self,
        entity: CanonicalEntity,
        facts: list[BusinessFact],
        agreement: Agreement | None,
        now: datetime,
    ) -> KnowledgeEvent:
        """Build a knowledge event from entity + facts."""
        # Determine event type
        event_type = KnowledgeEventType.CREATED
        entity_id = str(entity.id)

        # Check if entity has evidence (has been seen before)
        if entity.evidence:
            if agreement:
                event_type = KnowledgeEventType.UPDATED
            else:
                event_type = KnowledgeEventType.UPDATED

        # Description from entity
        description = f"Entity {entity.display_name or entity_id} ({entity.entity_type.value})"

        return KnowledgeEvent(
            event_id=KnowledgeEventId.generate(),
            event_type=event_type,
            entity_id=entity_id,
            agreement_id=str(agreement.id) if agreement else "",
            occurred_at=now,
            description=description,
        )

    def _build_delta(
        self,
        entity: CanonicalEntity,
        facts: list[BusinessFact],
        event: KnowledgeEvent,
    ) -> KnowledgeDelta:
        """Build a knowledge delta from entity state + facts."""
        changes: list[KnowledgeChange] = []

        # Identifier changes from facts
        for f in facts:
            if f.fact_type == FactType.DOCUMENT_HAS_PARTY and f.object_entity_id:
                changes.append(KnowledgeChange(
                    field="participant",
                    old_value=None,
                    new_value=f.object_entity_id,
                ))
            elif f.fact_type == FactType.DOCUMENT_HAS_AMOUNT and f.value:
                changes.append(KnowledgeChange(
                    field="amount",
                    old_value=None,
                    new_value=str(f.value),
                ))
            elif f.fact_type == FactType.DOCUMENT_HAS_DATE and f.value:
                changes.append(KnowledgeChange(
                    field="date",
                    old_value=None,
                    new_value=str(f.value),
                ))

        return KnowledgeDelta(
            entity_id=str(entity.id),
            event_id=event.event_id,
            changes=tuple(changes),
        )
