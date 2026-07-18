"""
Tests — Knowledge Evolution Services Phase A4.2.

Covers: ConflictDetector, TrustEvaluator, AuthorityEvaluator,
        KnowledgeEvolutionService, KnowledgeEvolutionResult.

ALL services: stateless, deterministic, side-effect free.
NO mutation. NO IO. NO DB.
"""
from __future__ import annotations

import pytest

from domain.business_relationship.ke_identifiers import KnowledgeEventId
from domain.business_relationship.ke_enums import (
    KnowledgeEventType, TrustLevel, AuthorityLevel, ConflictType,
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
from domain.business_relationship.ke_evolution_service import KnowledgeEvolutionService
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.identity_evidence import IdentityEvidence


# ── Helpers ──

def _make_prov() -> Provenance:
    return Provenance(document_revision=DocumentRevision(document_id="doc-1"))


def _make_fact(ftype: FactType, value: str = "") -> BusinessFact:
    return BusinessFact(
        fact_type=ftype, subject_entity_id="d", provenance=_make_prov(),
        id=FactId.generate(),
        value=FactValue.from_str(value) if value else None,
        confidence=FactConfidence.medium(),
    )


def _make_entity() -> CanonicalEntity:
    return CanonicalEntity(
        entity_type=EntityType.COMPANY,
        id=CanonicalEntityId.generate(),
        display_name="ООО Ромашка",
    )


def _make_agreement() -> Agreement:
    return Agreement(
        agreement_type=AgreementType.SALE,
        id=AgreementId.generate(),
        number="2182-НП/И",
    )


# ── KnowledgeEvolutionResult Tests ──

class TestKnowledgeEvolutionResult:
    def test_empty(self):
        r = KnowledgeEvolutionResult()
        assert len(r.events) == 0
        assert r.trust_level == TrustLevel.UNKNOWN

    def test_with_data(self):
        eid = KnowledgeEventId.generate()
        event = KnowledgeEvent(event_id=eid, event_type=KnowledgeEventType.CREATED, entity_id="e1")
        r = KnowledgeEvolutionResult(events=(event,), trust_level=TrustLevel.HIGH)
        assert len(r.events) == 1
        assert r.trust_level == TrustLevel.HIGH

    def test_immutable(self):
        r = KnowledgeEvolutionResult()
        with pytest.raises(Exception):
            r.events = ()


# ── KnowledgeEvolutionReport Tests ──

class TestKnowledgeEvolutionReport:
    def test_empty(self):
        r = KnowledgeEvolutionReport()
        assert r.total_events == 0

    def test_create(self):
        r = KnowledgeEvolutionReport(total_events=3, total_deltas=2, total_conflicts=1)
        assert r.total_events == 3
        assert r.total_deltas == 2

    def test_immutable(self):
        r = KnowledgeEvolutionReport()
        with pytest.raises(Exception):
            r.total_events = 5


# ── ConflictDetector Tests ──

class TestConflictDetector:
    def test_no_conflict(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate())
        conflicts = ConflictDetector.detect(delta)
        assert len(conflicts) == 0

    def test_ownership_conflict(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate(),
                               changes=(KnowledgeChange("ownership", "A", "B"),))
        conflicts = ConflictDetector.detect(delta)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.OWNERSHIP

    def test_participant_conflict(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate(),
                               changes=(KnowledgeChange("participant", "X", "Y"),))
        conflicts = ConflictDetector.detect(delta)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.PARTICIPANT

    def test_period_conflict(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate(),
                               changes=(KnowledgeChange("period", "2026-01-01", "2026-06-01"),))
        conflicts = ConflictDetector.detect(delta)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.PERIOD

    def test_multiple_fields(self):
        delta = KnowledgeDelta(
            entity_id="e1", event_id=KnowledgeEventId.generate(),
            changes=(
                KnowledgeChange("owner", "A", "B"),
                KnowledgeChange("participant", "C", "D"),
                KnowledgeChange("amount", "100", "200"),
            ),
        )
        conflicts = ConflictDetector.detect(delta)
        assert len(conflicts) == 3

    def test_deterministic(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate(),
                               changes=(KnowledgeChange("ownership", "A", "B"),))
        r1 = ConflictDetector.detect(delta)
        r2 = ConflictDetector.detect(delta)
        assert len(r1) == len(r2)
        assert r1[0].conflict_type == r2[0].conflict_type

    def test_no_resolve_method(self):
        assert not hasattr(ConflictDetector, 'resolve')
        assert not hasattr(ConflictDetector, 'apply')


# ── TrustEvaluator Tests ──

class TestTrustEvaluator:
    def test_official_verified(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1", authority_level=AuthorityLevel.OFFICIAL)
        assert TrustEvaluator.evaluate(event) == TrustLevel.VERIFIED

    def test_strong_conflict_resolved_high(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CONFLICT_RESOLVED,
                               entity_id="e1", authority_level=AuthorityLevel.STRONG)
        assert TrustEvaluator.evaluate(event) == TrustLevel.HIGH

    def test_with_agreement_medium(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.UPDATED,
                               entity_id="e1", agreement_id="ag-1")
        assert TrustEvaluator.evaluate(event) == TrustLevel.MEDIUM

    def test_created_low(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1")
        assert TrustEvaluator.evaluate(event) == TrustLevel.LOW

    def test_unknown_default(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CONFLICT_DETECTED,
                               entity_id="e1")
        assert TrustEvaluator.evaluate(event) == TrustLevel.UNKNOWN

    def test_deterministic(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1", authority_level=AuthorityLevel.OFFICIAL)
        assert TrustEvaluator.evaluate(event) == TrustEvaluator.evaluate(event)

    def test_no_calculate_method(self):
        assert not hasattr(TrustEvaluator, 'calculate')
        assert not hasattr(TrustEvaluator, 'compute')


# ── AuthorityEvaluator Tests ──

class TestAuthorityEvaluator:
    def test_official_source(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1", authority_level=AuthorityLevel.OFFICIAL)
        assert AuthorityEvaluator.evaluate(event) == AuthorityLevel.OFFICIAL

    def test_merged_strong(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.MERGED,
                               entity_id="e1")
        assert AuthorityEvaluator.evaluate(event) == AuthorityLevel.STRONG

    def test_with_agreement_normal(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.UPDATED,
                               entity_id="e1", agreement_id="ag-1")
        assert AuthorityEvaluator.evaluate(event) == AuthorityLevel.NORMAL

    def test_created_weak(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1")
        assert AuthorityEvaluator.evaluate(event) == AuthorityLevel.WEAK

    def test_unknown_default(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CONFLICT_DETECTED,
                               entity_id="e1")
        assert AuthorityEvaluator.evaluate(event) == AuthorityLevel.UNKNOWN

    def test_deterministic(self):
        event = KnowledgeEvent(event_id=KnowledgeEventId.generate(),
                               event_type=KnowledgeEventType.CREATED,
                               entity_id="e1")
        assert AuthorityEvaluator.evaluate(event) == AuthorityEvaluator.evaluate(event)


# ── KnowledgeEvolutionService Tests ──

class TestKnowledgeEvolutionService:
    def test_evolve_new_entity(self):
        service = KnowledgeEvolutionService()
        entity = _make_entity()
        result = service.evolve(entity=entity, facts=[])
        assert len(result.events) == 1

    def test_evolve_with_agreement(self):
        service = KnowledgeEvolutionService()
        entity = _make_entity()
        agreement = _make_agreement()
        result = service.evolve(entity=entity, facts=[], agreement=agreement)
        assert result.events[0].agreement_id == str(agreement.id)

    def test_evolve_with_facts(self):
        service = KnowledgeEvolutionService()
        entity = _make_entity()
        facts = [
            _make_fact(FactType.DOCUMENT_HAS_PARTY, "e-2"),
            _make_fact(FactType.DOCUMENT_HAS_AMOUNT, "5000000"),
        ]
        result = service.evolve(entity=entity, facts=facts)
        assert len(result.deltas) == 1
        assert len(result.deltas[0].changes) > 0

    def test_deterministic(self):
        service = KnowledgeEvolutionService()
        entity = _make_entity()
        r1 = service.evolve(entity=entity, facts=[])
        r2 = service.evolve(entity=entity, facts=[])
        assert r1.trust_level == r2.trust_level
        assert len(r1.events) == len(r2.events)

    def test_stateless(self):
        service = KnowledgeEvolutionService()
        e1 = _make_entity()
        e2 = _make_entity()
        r1 = service.evolve(entity=e1, facts=[])
        r2 = service.evolve(entity=e2, facts=[])
        assert r1 is not r2
        assert r1.events[0].entity_id != r2.events[0].entity_id

    def test_no_mutation(self):
        service = KnowledgeEvolutionService()
        entity = _make_entity()
        original_id = entity.id
        result = service.evolve(entity=entity, facts=[])
        assert entity.id == original_id  # Entity not modified
        assert len(result.events) == 1
