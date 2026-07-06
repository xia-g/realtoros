"""
Tests — Knowledge State & Change Tracking v2.0.6
Revisions, Deltas, Timelines, Explanations
"""
from __future__ import annotations

import pytest

from domain.business_relationship.knowledge_state import KnowledgeState, TrustSummary
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_delta import (
    KnowledgeChange, KnowledgeChangeType, KnowledgeDelta, ChangeCategory,
)
from domain.business_relationship.change_tracker import ChangeTracker
from domain.business_relationship.state_explanation import ChangeExplanation, TimelineEntry


# ── KnowledgeState Tests ──

class TestKnowledgeState:
    def test_state_immutable(self):
        s = KnowledgeState(entity_count=5, property_count=3)
        with pytest.raises(Exception):
            s.entity_count = 10

    def test_state_to_dict(self):
        s = KnowledgeState(entity_count=5)
        d = s.to_dict()
        assert d["entity_count"] == 5
        assert "graph_version" in d

    def test_trust_summary(self):
        ts = TrustSummary(verified_count=2, high_trust_count=2, medium_trust_count=1)
        assert ts.average_trust > 0


# ── KnowledgeRevision Tests ──

class TestKnowledgeRevision:
    def test_revision_immutable(self):
        s = KnowledgeState()
        r = KnowledgeRevision(revision_number=1, state=s)
        with pytest.raises(Exception):
            r.revision_number = 2

    def test_monotonic(self):
        s = KnowledgeState()
        r1 = KnowledgeRevision(revision_number=1, state=s)
        r2 = KnowledgeRevision(revision_number=2, state=s)
        assert r2.revision_number > r1.revision_number

    def test_revision_has_previous(self):
        s = KnowledgeState()
        r = KnowledgeRevision(revision_number=2, state=s, previous_revision=1)
        assert r.previous_revision == 1

    def test_revision_to_dict(self):
        s = KnowledgeState(entity_count=3)
        r = KnowledgeRevision(revision_number=5, state=s, summary="Added entities")
        d = r.to_dict()
        assert d["revision"] == 5
        assert d["summary"] == "Added entities"


# ── KnowledgeChange / Delta Tests ──

class TestKnowledgeDelta:
    def test_change_creation(self):
        c = KnowledgeChange(
            change_type=KnowledgeChangeType.ENTITY_CREATED,
            object_id="e-1",
            description="Новый контрагент: ООО Ромашка",
            confidence=0.95,
        )
        assert c.change_type == KnowledgeChangeType.ENTITY_CREATED
        assert c.object_id == "e-1"

    def test_change_immutable(self):
        c = KnowledgeChange(KnowledgeChangeType.FACT_CONFIRMED, "e-1", "test")
        with pytest.raises(Exception):
            c.object_id = "e-2"

    def test_delta_has_changes(self):
        c = KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-1", "New")
        d = KnowledgeDelta(from_revision=1, to_revision=2, changes=[c], summary="+1 entity")
        assert d.has_changes

    def test_delta_by_category(self):
        c1 = KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-1", "New")
        c2 = KnowledgeChange(KnowledgeChangeType.OWNERSHIP_CONFIRMED, "p-1", "Confirmed")
        d = KnowledgeDelta(1, 2, changes=[c1, c2])
        cats = d.by_category()
        assert ChangeCategory.ENTITIES in cats
        assert ChangeCategory.OWNERSHIP in cats

    def test_change_type_to_category(self):
        assert ChangeCategory.from_change_type(KnowledgeChangeType.ENTITY_CREATED) == ChangeCategory.ENTITIES
        assert ChangeCategory.from_change_type(KnowledgeChangeType.OWNERSHIP_CONFIRMED) == ChangeCategory.OWNERSHIP

    def test_delta_all_change_types(self):
        for ct in KnowledgeChangeType:
            c = KnowledgeChange(ct, "obj-1", "test")
            d = KnowledgeDelta(1, 2, changes=[c])
            assert d.has_changes


# ── ChangeTracker Tests ──

class TestChangeTracker:
    def test_create_revision(self):
        tracker = ChangeTracker()
        s = KnowledgeState(entity_count=1)
        r = tracker.create_revision(state=s)
        assert r.revision_number == 1
        assert tracker.revision_count == 1

    def test_revision_monotonic(self):
        tracker = ChangeTracker()
        r1 = tracker.create_revision(KnowledgeState(entity_count=1))
        r2 = tracker.create_revision(KnowledgeState(entity_count=2))
        assert r2.revision_number > r1.revision_number
        assert r2.previous_revision == r1.revision_number

    def test_latest_revision(self):
        tracker = ChangeTracker()
        tracker.create_revision(KnowledgeState(entity_count=1))
        tracker.create_revision(KnowledgeState(entity_count=2))
        latest = tracker.latest_revision
        assert latest is not None
        assert latest.state.entity_count == 2

    def test_revision_with_changes(self):
        tracker = ChangeTracker()
        changes = [KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-1", "Test")]
        r = tracker.create_revision(KnowledgeState(entity_count=1), document_ids=["doc-1"], changes=changes)
        assert r.summary != ""

    def test_delta_non_destructive(self):
        tracker = ChangeTracker()
        s1 = KnowledgeState(entity_count=1)
        s2 = KnowledgeState(entity_count=3)
        r1 = tracker.create_revision(s1)
        r2 = tracker.create_revision(s2)

        changes = [
            KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-1", "Entity 1"),
            KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-2", "Entity 2"),
        ]
        delta = tracker.calculate_delta(r1, r2, changes)
        assert delta.from_revision == 1
        assert delta.to_revision == 2
        assert delta.has_changes

    def test_timeline(self):
        tracker = ChangeTracker()
        changes = [KnowledgeChange(KnowledgeChangeType.ENTITY_CREATED, "e-1", "Created")]
        tracker.create_revision(KnowledgeState(entity_count=1), changes=changes)
        timeline = tracker.get_timeline("e-1")
        assert len(timeline) == 1
        assert timeline[0].change_type == "entity_created"

    def test_timeline_empty_for_unknown(self):
        tracker = ChangeTracker()
        tl = tracker.get_timeline("unknown-entity")
        assert len(tl) == 0

    def test_explain_change(self):
        tracker = ChangeTracker()
        c = KnowledgeChange(KnowledgeChangeType.OWNERSHIP_CONFIRMED, "p-1",
                            "Подтверждено право собственности",
                            source_document_ids=["doc-1", "doc-2"])
        exp = tracker.explain_change(c)
        assert len(exp.supporting_documents) == 2
        assert exp.confidence > 0

    def test_revision_append_only(self):
        tracker = ChangeTracker()
        tracker.create_revision(KnowledgeState(entity_count=1))
        tracker.create_revision(KnowledgeState(entity_count=2))
        revisions = tracker._revisions
        assert len(revisions) == 2
        assert revisions[0].state.entity_count == 1
        assert revisions[1].state.entity_count == 2


# ── Explanation Tests ──

class TestExplanation:
    def test_explanation_immutable(self):
        e = ChangeExplanation(summary="Test", evidence=["doc-1"], confidence=0.9)
        with pytest.raises(Exception):
            e.summary = "Changed"

    def test_timeline_entry(self):
        t = TimelineEntry(revision_number=1, change_type="entity_created", description="Test", confidence=0.95)
        assert t.to_dict()["revision"] == 1
