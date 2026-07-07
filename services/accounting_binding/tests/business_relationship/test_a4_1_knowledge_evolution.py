"""
Tests — Knowledge Evolution Domain Model Phase A4.1.

All models: immutable, no logic, no apply/resolve/calculate.
NO Domain Services. NO algorithms. NO heuristics.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from domain.business_relationship.ke_identifiers import KnowledgeEventId
from domain.business_relationship.ke_enums import (
    KnowledgeEventType, TrustLevel, AuthorityLevel, ConflictType,
)
from domain.business_relationship.ke_event import KnowledgeEvent
from domain.business_relationship.ke_change import KnowledgeChange
from domain.business_relationship.ke_delta import KnowledgeDelta
from domain.business_relationship.ke_conflict import KnowledgeConflict
from domain.business_relationship.ke_timeline_entry import KnowledgeTimelineEntry
from domain.business_relationship.ke_metadata import KnowledgeMetadata


# ── KnowledgeEventId Tests ──

class TestKnowledgeEventId:
    def test_generate(self):
        eid = KnowledgeEventId.generate()
        assert bool(eid)

    def test_from_string(self):
        eid = KnowledgeEventId.from_string("ke-1")
        assert eid.value == "ke-1"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            KnowledgeEventId.from_string("")

    def test_immutable(self):
        eid = KnowledgeEventId(value="x")
        with pytest.raises(Exception):
            eid.value = "y"

    def test_equality(self):
        assert KnowledgeEventId(value="x") == KnowledgeEventId(value="x")
        assert KnowledgeEventId(value="x") != KnowledgeEventId(value="y")


# ── Enum Tests ──

class TestKnowledgeEventType:
    def test_all_values(self):
        for t in KnowledgeEventType:
            assert t.value

    def test_created_exists(self):
        assert KnowledgeEventType.CREATED.value == "created"
        assert KnowledgeEventType.SUPERSEDED.value == "superseded"
        assert KnowledgeEventType.CONFLICT_DETECTED.value == "conflict_detected"


class TestTrustLevel:
    def test_values(self):
        assert TrustLevel.UNKNOWN.value == "unknown"
        assert TrustLevel.HIGH.value == "high"
        assert TrustLevel.VERIFIED.value == "verified"

    def test_ordering_not_defined(self):
        """TrustLevel has no ordering logic — just enum values."""
        assert TrustLevel.LOW.value == "low"
        assert TrustLevel.HIGH.value == "high"


class TestAuthorityLevel:
    def test_values(self):
        assert AuthorityLevel.WEAK.value == "weak"
        assert AuthorityLevel.OFFICIAL.value == "official"


class TestConflictType:
    def test_values(self):
        assert ConflictType.IDENTITY.value == "identity"
        assert ConflictType.OWNERSHIP.value == "ownership"


# ── KnowledgeEvent Tests ──

class TestKnowledgeEvent:
    def test_create(self):
        eid = KnowledgeEventId.generate()
        event = KnowledgeEvent(
            event_id=eid,
            event_type=KnowledgeEventType.CREATED,
            entity_id="ce-1",
        )
        assert event.event_id == eid
        assert event.event_type == KnowledgeEventType.CREATED
        assert event.entity_id == "ce-1"

    def test_full(self):
        event = KnowledgeEvent(
            event_id=KnowledgeEventId.generate(),
            event_type=KnowledgeEventType.MERGED,
            entity_id="ce-1",
            agreement_id="ag-1",
            occurred_at=datetime(2026, 7, 7),
            trust_level=TrustLevel.HIGH,
            authority_level=AuthorityLevel.OFFICIAL,
            description="Entity merged with ce-2",
        )
        assert event.agreement_id == "ag-1"
        assert event.trust_level == TrustLevel.HIGH
        assert event.description == "Entity merged with ce-2"

    def test_immutable(self):
        event = KnowledgeEvent(
            event_id=KnowledgeEventId.generate(),
            event_type=KnowledgeEventType.CREATED,
            entity_id="e1",
        )
        with pytest.raises(Exception):
            event.entity_id = "changed"

    def test_equality(self):
        eid = KnowledgeEventId(value="x")
        e1 = KnowledgeEvent(event_id=eid, event_type=KnowledgeEventType.CREATED, entity_id="e1")
        e2 = KnowledgeEvent(event_id=eid, event_type=KnowledgeEventType.CREATED, entity_id="e1")
        assert e1 == e2

    def test_no_apply_method(self):
        """KnowledgeEvent must NOT have apply(), resolve(), execute()."""
        event = KnowledgeEvent(
            event_id=KnowledgeEventId.generate(),
            event_type=KnowledgeEventType.CREATED,
            entity_id="e1",
        )
        assert not hasattr(event, 'apply')
        assert not hasattr(event, 'resolve')
        assert not hasattr(event, 'execute')
        assert not hasattr(event, 'calculate')


# ── KnowledgeChange Tests ──

class TestKnowledgeChange:
    def test_create(self):
        c = KnowledgeChange(field="trust_level", old_value="low", new_value="high")
        assert c.field == "trust_level"
        assert c.old_value == "low"
        assert c.new_value == "high"

    def test_immutable(self):
        c = KnowledgeChange(field="x")
        with pytest.raises(Exception):
            c.field = "y"

    def test_no_apply_method(self):
        c = KnowledgeChange(field="x")
        assert not hasattr(c, 'apply')
        assert not hasattr(c, 'execute')

    def test_equality(self):
        assert KnowledgeChange("x", 1, 2) == KnowledgeChange("x", 1, 2)
        assert KnowledgeChange("x", 1, 2) != KnowledgeChange("y", 1, 2)


# ── KnowledgeDelta Tests ──

class TestKnowledgeDelta:
    def test_create(self):
        eid = KnowledgeEventId.generate()
        changes = (KnowledgeChange("trust", "low", "high"),)
        delta = KnowledgeDelta(entity_id="ce-1", event_id=eid, changes=changes)
        assert delta.entity_id == "ce-1"
        assert len(delta.changes) == 1

    def test_empty_changes(self):
        delta = KnowledgeDelta(
            entity_id="ce-1",
            event_id=KnowledgeEventId.generate(),
        )
        assert len(delta.changes) == 0

    def test_immutable(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate())
        with pytest.raises(Exception):
            delta.entity_id = "changed"

    def test_no_merge_method(self):
        delta = KnowledgeDelta(entity_id="e1", event_id=KnowledgeEventId.generate())
        assert not hasattr(delta, 'merge')
        assert not hasattr(delta, 'apply')
        assert not hasattr(delta, 'execute')


# ── KnowledgeConflict Tests ──

class TestKnowledgeConflict:
    def test_create(self):
        conflict = KnowledgeConflict(
            conflict_type=ConflictType.IDENTITY,
            entity_id="ce-1",
            conflicting_sources=("doc-1", "doc-2"),
            description="Two different INNs for same entity",
        )
        assert conflict.conflict_type == ConflictType.IDENTITY
        assert len(conflict.conflicting_sources) == 2

    def test_immutable(self):
        conflict = KnowledgeConflict(conflict_type=ConflictType.OTHER, entity_id="e1")
        with pytest.raises(Exception):
            conflict.entity_id = "changed"

    def test_no_resolve_method(self):
        conflict = KnowledgeConflict(conflict_type=ConflictType.OTHER, entity_id="e1")
        assert not hasattr(conflict, 'resolve')
        assert not hasattr(conflict, 'apply')

    def test_all_types(self):
        for ct in ConflictType:
            c = KnowledgeConflict(conflict_type=ct, entity_id="e1")
            assert c.conflict_type == ct


# ── KnowledgeTimelineEntry Tests ──

class TestKnowledgeTimelineEntry:
    def test_create(self):
        ts = datetime(2026, 7, 7)
        entry = KnowledgeTimelineEntry(
            timestamp=ts,
            event_id=KnowledgeEventId(value="ke-1"),
            entity_id="ce-1",
            summary="Entity was created",
        )
        assert entry.timestamp == ts
        assert entry.summary == "Entity was created"

    def test_immutable(self):
        entry = KnowledgeTimelineEntry(
            timestamp=datetime(2026, 1, 1),
            event_id=KnowledgeEventId.generate(),
            entity_id="e1",
            summary="test",
        )
        with pytest.raises(Exception):
            entry.summary = "changed"


# ── KnowledgeMetadata Tests ──

class TestKnowledgeMetadata:
    def test_defaults(self):
        m = KnowledgeMetadata()
        assert m.revision_hint == 0
        assert m.source_count == 0

    def test_create(self):
        m = KnowledgeMetadata(created_by="ocr_v2", revision_hint=5, source_count=3)
        assert m.created_by == "ocr_v2"
        assert m.revision_hint == 5
        assert m.source_count == 3

    def test_immutable(self):
        m = KnowledgeMetadata()
        with pytest.raises(Exception):
            m.created_by = "changed"


# ── Regression: NO Domain Services ──

class TestNoDomainServices:
    """Verify that NO domain services are implemented in A4.1."""

    def test_no_knowledge_evolution_service(self):
        """KnowledgeEvolutionService must NOT exist in A4.1."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import domain.business_relationship.knowledge_evolution_service  # noqa

    def test_no_conflict_resolver(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import domain.business_relationship.conflict_resolver  # noqa

    def test_no_trust_evaluator(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import domain.business_relationship.trust_evaluator  # noqa

    def test_no_authority_evaluator(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import domain.business_relationship.authority_evaluator  # noqa

    def test_no_evolution_engine(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            import domain.business_relationship.evolution_engine  # noqa
