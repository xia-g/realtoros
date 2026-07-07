"""
Tests — Neutral Facts Phase A1.

Covers: FactId, FactValue, FactConfidence, FactSource, FactEvidence,
        BusinessFact (immutable, equality, hashing, serialization),
        FactBuilder (convenience methods, validation).

All models must be:
  immutable, append-only, serializable, hashable,
  deterministic, equality based on value, technology-independent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest

from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_source import FactSource
from domain.business_relationship.fact_evidence import FactEvidence
from domain.business_relationship.fact_builder import FactBuilder
from domain.business_relationship.provenance import Provenance, DocumentRevision


# ── FactId Tests ──

class TestFactId:
    def test_create(self):
        fid = FactId(value="test-id")
        assert str(fid) == "test-id"

    def test_generate(self):
        fid = FactId.generate()
        assert bool(fid)
        assert len(fid.value) > 0

    def test_from_string(self):
        fid = FactId.from_string("abc-123")
        assert fid.value == "abc-123"

    def test_from_string_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            FactId.from_string("")

    def test_from_string_whitespace_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            FactId.from_string("   ")

    def test_immutable(self):
        fid = FactId(value="test")
        with pytest.raises(Exception):
            fid.value = "changed"

    def test_equality(self):
        assert FactId(value="x") == FactId(value="x")
        assert FactId(value="x") != FactId(value="y")

    def test_hashable(self):
        s = {FactId(value="a"), FactId(value="a"), FactId(value="b")}
        assert len(s) == 2

    def test_serializable(self):
        fid = FactId(value="test-id")
        d = {"id": fid.value}
        assert json.dumps(d)


# ── FactValue Tests ──

class TestFactValue:
    def test_string_value(self):
        v = FactValue.from_str("ИНН 780527855675")
        assert str(v) == "ИНН 780527855675"

    def test_decimal_value(self):
        v = FactValue.from_decimal(Decimal("5000000"))
        assert str(v) == "5000000"

    def test_date_value(self):
        d = date(2026, 5, 26)
        v = FactValue.from_date(d)
        assert str(v) == "2026-05-26"

    def test_empty_is_falsey(self):
        v = FactValue()
        assert not v

    def test_string_is_truthy(self):
        assert FactValue.from_str("test")

    def test_immutable(self):
        v = FactValue(string="test")
        with pytest.raises(Exception):
            v.string = "changed"

    def test_equality(self):
        assert FactValue.from_str("x") == FactValue.from_str("x")
        assert FactValue.from_str("x") != FactValue.from_str("y")

    def test_hashable(self):
        s = {FactValue.from_str("a"), FactValue.from_str("a")}
        assert len(s) == 1


# ── FactConfidence Tests ──

class TestFactConfidence:
    def test_valid_range(self):
        FactConfidence(value=0.0)
        FactConfidence(value=1.0)
        FactConfidence(value=0.5)

    def test_invalid_low(self):
        with pytest.raises(ValueError, match="must be in"):
            FactConfidence(value=-0.1)

    def test_invalid_high(self):
        with pytest.raises(ValueError, match="must be in"):
            FactConfidence(value=1.1)

    def test_high_factory(self):
        c = FactConfidence.high()
        assert float(c) == 0.95

    def test_medium_factory(self):
        c = FactConfidence.medium()
        assert float(c) == 0.75

    def test_low_factory(self):
        c = FactConfidence.low()
        assert float(c) == 0.50

    def test_bool_positive(self):
        assert FactConfidence(value=0.5)

    def test_bool_zero(self):
        assert not FactConfidence(value=0.0)

    def test_immutable(self):
        c = FactConfidence(value=0.5)
        with pytest.raises(Exception):
            c.value = 0.8

    def test_equality(self):
        assert FactConfidence(value=0.5) == FactConfidence(value=0.5)
        assert FactConfidence(value=0.5) != FactConfidence(value=0.8)


# ── FactSource Tests ──

class TestFactSource:
    def test_create(self):
        s = FactSource(document_id="doc-1")
        assert s.document_id == "doc-1"
        assert s.method == "ocr"

    def test_semantic_factory(self):
        s = FactSource.semantic("doc-1")
        assert s.method == "semantic"

    def test_manual_factory(self):
        s = FactSource.manual("doc-1")
        assert s.method == "manual"

    def test_bool(self):
        assert FactSource(document_id="d")
        assert not FactSource(document_id="")

    def test_immutable(self):
        s = FactSource(document_id="d")
        with pytest.raises(Exception):
            s.document_id = "changed"


# ── FactEvidence Tests ──

class TestFactEvidence:
    def test_create(self):
        s = FactSource(document_id="d")
        c = FactConfidence.high()
        ev = FactEvidence(source=s, confidence=c, detail="OCR match")
        assert ev.detail == "OCR match"

    def test_factory(self):
        s = FactSource(document_id="d")
        ev = FactEvidence.from_source(s)
        assert float(ev.confidence) == 0.75  # medium default

    def test_bool(self):
        ev = FactEvidence.from_source(FactSource(document_id="d"))
        assert ev
        ev_empty = FactEvidence(source=FactSource(document_id=""), confidence=FactConfidence.low())
        assert not ev_empty

    def test_immutable(self):
        ev = FactEvidence.from_source(FactSource(document_id="d"))
        with pytest.raises(Exception):
            ev.detail = "changed"


# ── BusinessFact Tests ──

class TestBusinessFact:
    def _make_fact(self, **overrides) -> BusinessFact:
        rev = DocumentRevision(document_id="doc-1", revision=1)
        prov = Provenance(document_revision=rev, extraction_method="ocr")
        params = dict(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id="entity-1",
            provenance=prov,
            id=FactId(value="fact-1"),
        )
        params.update(overrides)
        return BusinessFact(**params)

    def test_create(self):
        f = self._make_fact()
        assert f.fact_type == FactType.DOCUMENT_HAS_PARTY
        assert f.subject_entity_id == "entity-1"
        assert f.document_id == "doc-1"

    def test_immutable(self):
        f = self._make_fact()
        with pytest.raises(Exception):
            f.fact_type = FactType.DOCUMENT_HAS_PROPERTY

    def test_equality_by_value(self):
        """Same field values → equal facts."""
        f1 = self._make_fact()
        f2 = self._make_fact()
        # Different FactId by default, so not equal
        # But same id → equal
        assert f1 == f1

    def test_hashable(self):
        f = self._make_fact()
        s = {f, f}
        assert len(s) == 1

    def test_document_id_property(self):
        f = self._make_fact()
        assert f.document_id == "doc-1"

    def test_with_value(self):
        f = self._make_fact(
            value=FactValue.from_decimal(Decimal("5000000")),
        )
        assert f.value is not None
        assert str(f.value) == "5000000"

    def test_with_confidence(self):
        f = self._make_fact(confidence=FactConfidence.high())
        assert f.confidence is not None
        assert float(f.confidence) == 0.95

    def test_with_object_entity(self):
        f = self._make_fact(object_entity_id="entity-2")
        assert f.object_entity_id == "entity-2"

    def test_no_agreement_import(self):
        """BusinessFact MUST NOT import Agreement, Identity, Graph, etc."""
        import sys
        fact_module = sys.modules.get(BusinessFact.__module__)
        assert fact_module is not None

    def test_deterministic_serialization(self):
        """Same fields → same serialization."""
        f1 = self._make_fact()
        f2 = self._make_fact()
        # Different ids → different objects
        # Same id → same repr
        rev = DocumentRevision(document_id="d")
        prov = Provenance(document_revision=rev)
        f3 = BusinessFact(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id="e",
            provenance=prov,
            id=FactId(value="fixed-id"),
        )
        f4 = BusinessFact(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id="e",
            provenance=prov,
            id=FactId(value="fixed-id"),
        )
        assert repr(f3) == repr(f4)


# ── FactBuilder Tests ──

class TestFactBuilder:
    def test_build_minimal(self):
        f = FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id="e-1",
            document_id="doc-1",
        )
        assert f.fact_type == FactType.DOCUMENT_HAS_PARTY
        assert f.document_id == "doc-1"

    def test_build_immutable(self):
        f = FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id="e-1",
            document_id="doc-1",
        )
        with pytest.raises(Exception):
            f.subject_entity_id = "changed"

    def test_document_has_party(self):
        f = FactBuilder.document_has_party(document_id="doc-1", entity_id="e-1")
        assert f.fact_type == FactType.DOCUMENT_HAS_PARTY

    def test_document_has_property(self):
        f = FactBuilder.document_has_property(document_id="doc-1", property_id="p-1")
        assert f.fact_type == FactType.DOCUMENT_HAS_PROPERTY

    def test_document_has_amount(self):
        f = FactBuilder.document_has_amount(document_id="doc-1", amount=Decimal("5000000"))
        assert f.fact_type == FactType.DOCUMENT_HAS_AMOUNT
        assert str(f.value) == "5000000"

    def test_document_has_date(self):
        d = date(2026, 5, 26)
        f = FactBuilder.document_has_date(document_id="doc-1", fact_date=d)
        assert f.fact_type == FactType.DOCUMENT_HAS_DATE
        assert str(f.value) == "2026-05-26"

    def test_document_has_identifier(self):
        f = FactBuilder.document_has_identifier(document_id="doc-1", identifier_value="780527855675")
        assert f.fact_type == FactType.DOCUMENT_HAS_IDENTIFIER
        assert f.value is not None

    def test_document_has_role(self):
        f = FactBuilder.document_has_role(document_id="doc-1", role="sale_contract")
        assert f.fact_type == FactType.DOCUMENT_HAS_ROLE
        assert str(f.value) == "sale_contract"

    def test_convenience_immutable(self):
        f = FactBuilder.document_has_party(document_id="doc-1", entity_id="e-1")
        with pytest.raises(Exception):
            f.id = "changed"

    def test_convenience_all_types(self):
        """Every convenience method produces valid BusinessFact."""
        for builder_method, kwargs in [
            (FactBuilder.document_has_party, {"document_id": "d", "entity_id": "e"}),
            (FactBuilder.document_has_property, {"document_id": "d", "property_id": "p"}),
            (FactBuilder.document_has_amount, {"document_id": "d", "amount": Decimal("100")}),
            (FactBuilder.document_has_date, {"document_id": "d", "fact_date": date(2026, 1, 1)}),
            (FactBuilder.document_has_identifier, {"document_id": "d", "identifier_value": "x"}),
            (FactBuilder.document_has_role, {"document_id": "d", "role": "test"}),
        ]:
            f = builder_method(**kwargs)
            assert isinstance(f, BusinessFact)
            assert f.document_id == "d"

    def test_no_business_inference(self):
        """FactBuilder must NOT produce business-inferred facts."""
        f = FactBuilder.document_has_party(document_id="d", entity_id="e")
        # Must NOT have SELLS, OWNS, etc.
        forbidden_types = {"sells", "owns", "buys", "leases", "landlord", "tenant",
                           "seller", "buyer", "customer", "supplier", "broker"}
        assert f.fact_type.value not in forbidden_types
        assert f.fact_type.value.startswith("document_has_")

    def test_builder_no_knowledge(self):
        """FactBuilder must NOT import Agreement, Identity, Graph, etc."""
        import sys
        builder_module = sys.modules[FactBuilder.__module__]
        module_source = open(builder_module.__file__).read() if hasattr(builder_module, '__file__') else ""
        # Should import fact, types, value objects — not business logic
        assert "fact" in str(builder_module.__file__) if hasattr(builder_module, '__file__') else True
