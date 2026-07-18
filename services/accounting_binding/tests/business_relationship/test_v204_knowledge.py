"""
Tests — Business Relationship Engine v2.0.4
Knowledge Events + Trust + Authority + Conflict + Evolution
"""
from __future__ import annotations

import pytest

from domain.business_relationship.knowledge_events import (
    KnowledgeEvent, KnowledgeEventType, EventVersion,
    entity_created, entity_matched, alias_added, property_matched,
    agreement_matched, confidence_updated, trust_updated,
    conflict_detected, conflict_resolved, knowledge_superseded,
)
from domain.business_relationship.trust import TrustScore, TrustLevel
from domain.business_relationship.authority import AuthorityResolver, AuthorityLevel
from domain.business_relationship.conflict import (
    KnowledgeConflict, ConflictDetector, ConflictStatus, ConflictCandidate,
)
from domain.business_relationship.knowledge_evolution import (
    KnowledgeEvolutionService, KnowledgeEvolutionResult, KnowledgeExplanation,
)


# ── Knowledge Events Tests ──

class TestKnowledgeEvents:
    def test_entity_created_event(self):
        ev = entity_created("e-1", "doc-1", {"display_name": "Test"})
        assert ev.event_type == KnowledgeEventType.ENTITY_CREATED
        assert ev.entity_id == "e-1"
        assert ev.payload["display_name"] == "Test"

    def test_event_immutable(self):
        ev = entity_created("e-1", "doc-1")
        with pytest.raises(Exception):
            ev.entity_id = "e-2"  # frozen

    def test_entity_matched(self):
        ev = entity_matched("e-1", "doc-2", "Existing Corp")
        assert ev.event_type == KnowledgeEventType.ENTITY_MATCHED
        assert ev.payload["matched_existing"] == "Existing Corp"

    def test_alias_added(self):
        ev = alias_added("e-1", "ООО Тест", "ооо тест", "doc-1")
        assert ev.payload["original"] == "ООО Тест"

    def test_property_matched(self):
        ev = property_matched("p-1", "78:10:0005522:3018", "doc-1")
        assert ev.payload["cadastral_number"] == "78:10:0005522:3018"

    def test_agreement_matched(self):
        ev = agreement_matched("a-1", "2182-НП/И", "doc-1")
        assert ev.payload["agreement_number"] == "2182-НП/И"

    def test_confidence_updated(self):
        ev = confidence_updated("e-1", 0.0, 0.5, "doc-2")
        assert ev.payload["new_confidence"] == 0.5

    def test_trust_updated(self):
        ev = trust_updated("e-1", "unknown", "medium", "doc-3")
        assert ev.payload["new_trust"] == "medium"

    def test_conflict_detected(self):
        ev = conflict_detected("e-1", "area", ["55.2", "56.1"], "doc-1")
        assert ev.payload["field"] == "area"

    def test_conflict_resolved(self):
        ev = conflict_resolved("e-1", "area", "55.2", "doc-2")
        assert ev.payload["resolved_to"] == "55.2"

    def test_knowledge_superseded(self):
        ev = knowledge_superseded("e-1", "e-2", "merged", "doc-1")
        assert ev.payload["superseded_by"] == "e-2"

    def test_event_version(self):
        ev = entity_created("e-1", "d-1")
        assert ev.event_version == EventVersion.V1_0.value

    def test_to_dict(self):
        ev = entity_created("e-1", "d-1", {"name": "X"})
        d = ev.to_dict()
        assert d["event_type"] == "entity_created"
        assert "timestamp" in d


# ── Trust Tests ──

class TestTrust:
    def test_initial_trust_unknown(self):
        ts = TrustScore(entity_id="e-1")
        assert ts.current_level == TrustLevel.UNKNOWN

    def test_trust_increases_with_evidence(self):
        ts = TrustScore(entity_id="e-1")
        ts.add_evidence("doc-1")
        assert ts.current_level == TrustLevel.LOW
        ts.add_evidence("doc-2")
        assert ts.current_level == TrustLevel.MEDIUM

    def test_official_source_boosts_trust(self):
        ts = TrustScore(entity_id="e-1")
        ts.add_evidence("doc-1", is_official=True)
        assert ts.current_level in (TrustLevel.LOW, TrustLevel.MEDIUM)

    def test_trust_history_recorded(self):
        ts = TrustScore(entity_id="e-1")
        ts.add_evidence("doc-1")
        assert len(ts.history) >= 1

    def test_trust_score_numeric(self):
        ts = TrustScore(entity_id="e-1")
        ts.add_evidence("d1")
        ts.add_evidence("d2")
        assert ts.score > 0.2


# ── Authority Tests ──

class TestAuthority:
    def test_egrn_is_official(self):
        ar = AuthorityResolver()
        assert ar.resolve("egrn_extract") == AuthorityLevel.OFFICIAL

    def test_sale_contract_is_high(self):
        ar = AuthorityResolver()
        assert ar.resolve("sale_contract") == AuthorityLevel.HIGH

    def test_invoice_is_normal(self):
        ar = AuthorityResolver()
        assert ar.resolve("invoice") == AuthorityLevel.NORMAL

    def test_unknown_is_very_low(self):
        ar = AuthorityResolver()
        assert ar.resolve("something_unknown") == AuthorityLevel.VERY_LOW

    def test_weight_comparison(self):
        ar = AuthorityResolver()
        assert ar.compare("egrn_extract", "invoice") > 0
        assert ar.compare("receipt", "passport") < 0

    def test_configurable_map(self):
        custom_map = {"custom_doc": AuthorityLevel.HIGH}
        ar = AuthorityResolver(authority_map=custom_map)
        assert ar.resolve("custom_doc") == AuthorityLevel.HIGH
        assert ar.resolve("invoice") == AuthorityLevel.VERY_LOW  # not in custom map

    def test_weight_numeric(self):
        ar = AuthorityResolver()
        assert ar.weight("egrn_extract") == 1.0
        assert ar.weight("invoice") == 0.5


# ── Conflict Tests ──

class TestConflict:
    def test_open_conflict(self):
        c = KnowledgeConflict(entity_id="e-1", field_name="area")
        c.add_candidate("55.2", authority="high")
        c.add_candidate("56.1", authority="normal")
        assert c.is_open
        assert len(c.candidates) == 2

    def test_resolve_conflict(self):
        c = KnowledgeConflict(entity_id="e-1", field_name="area")
        c.add_candidate("55.2", authority="high")
        c.add_candidate("56.1", authority="normal")
        c.resolve("55.2")
        assert c.status == ConflictStatus.RESOLVED
        assert c.resolved_to == "55.2"

    def test_ignore_conflict(self):
        c = KnowledgeConflict(entity_id="e-1", field_name="address")
        c.add_candidate("old", authority="normal")
        c.add_candidate("new", authority="normal")
        c.ignore()
        assert c.status == ConflictStatus.IGNORED

    def test_conflict_detector_no_difference(self):
        c = ConflictDetector.detect("e-1", "name", "Same", "Same")
        assert c is None

    def test_conflict_detector_with_difference(self):
        c = ConflictDetector.detect("e-1", "area", "55.2", "56.1")
        assert c is not None
        assert len(c.candidates) == 2

    def test_auto_resolve_by_authority(self):
        c = KnowledgeConflict(entity_id="e-1", field_name="area")
        c.add_candidate("wrong", authority="normal")
        c.add_candidate("correct", authority="official")
        result = ConflictDetector.resolve_by_authority(c)
        assert result == "correct"


# ── Knowledge Evolution Tests ──

class TestKnowledgeEvolution:
    def test_entity_created_registers_event(self):
        evo = KnowledgeEvolutionService()
        ev = evo.on_entity_created("e-1", "doc-1", "Test")
        assert ev.event_type == KnowledgeEventType.ENTITY_CREATED
        events = evo.get_events("e-1")
        assert len(events) == 1

    def test_entity_matched_updates_trust(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test")
        evo.on_entity_matched("e-1", "doc-2", "Test", "sale_contract")
        ts = evo.get_trust("e-1")
        assert ts is not None

    def test_alias_added(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test")
        evo.on_alias_added("e-1", "ООО Тест", "ооо тест", "doc-1")
        events = evo.get_events("e-1")
        assert any(e.event_type == KnowledgeEventType.ALIAS_ADDED for e in events)

    def test_conflict_check(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test")
        c = evo.check_conflict("e-1", "area", "55.2", "56.1", "doc-2")
        assert c is not None
        assert len(evo.get_conflicts()) == 1

    def test_timeline(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test")
        evo.on_alias_added("e-1", "A", "a", "doc-2")
        timeline = evo.get_timeline("e-1")
        assert len(timeline) == 2

    def test_explanation(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test Co")
        evo.on_entity_matched("e-1", "doc-2", "Test Co", "sale_contract")
        exp = evo.get_explanation("e-1")
        assert exp is not None
        assert len(exp.supporting_events) > 0

    def test_result_contains_all(self):
        evo = KnowledgeEvolutionService()
        evo.on_entity_created("e-1", "doc-1", "Test")
        result = evo.result()
        assert len(result.events) >= 1
        assert isinstance(result, KnowledgeEvolutionResult)
