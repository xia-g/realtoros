"""
Tests — Business Relationship Engine v2.0.1a (Hardening).

Neutral extraction: NO business interpretation.
Facts describe ONLY what is in the document.
"""
from __future__ import annotations

from datetime import date

import pytest

from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_resolver import EntityResolver
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.entity_extractor import EntityExtractor
from domain.business_relationship.fact_extractor import FactExtractor
from domain.business_relationship.extraction_context import ExtractionContext
from domain.business_relationship.document_reference import DocumentReference, ReferenceType


# ── Entity Tests (unchanged) ──

class TestEntityCreation:
    def test_basic_entity(self):
        e = BusinessEntity(entity_type=EntityType.COMPANY, display_name="ООО Тест")
        assert e.entity_type == EntityType.COMPANY

    def test_document_entity(self):
        e = BusinessEntity(entity_type=EntityType.DOCUMENT, display_name="2182-НП/И")
        assert e.entity_type == EntityType.DOCUMENT


class TestIdentifierNormalization:
    def test_inn_normalization(self):
        v = EntityIdentifier.normalize("7805.2785.5675", IdentifierType.INN)
        assert v == "780527855675"

    def test_contract_number_normalization(self):
        v = EntityIdentifier.normalize("  №2182-НП/И ", IdentifierType.CONTRACT_NUMBER)
        assert "2182-НП/И" in v


class TestEntityDedup:
    def test_dedup_by_inn(self):
        resolver = EntityResolver()
        idf = EntityIdentifier(IdentifierType.INN, "780527855675", "", confidence=0.95)
        e1, _ = resolver.resolve([idf])
        idf2 = EntityIdentifier(IdentifierType.INN, "780527855675", "", confidence=0.90)
        e2, _ = resolver.resolve([idf2])
        assert e1.id == e2.id


# ── Document Reference Tests ──

class TestDocumentReference:
    def test_act_for_reference(self):
        rev = DocumentRevision(document_id="akt-1")
        p = Provenance(document_revision=rev)
        ref = DocumentReference(
            reference_type=ReferenceType.ACT_FOR,
            source_document_id="akt-1",
            target_document_identifier="2182-НП/И",
            provenance=p,
            confidence=0.80,
        )
        assert ref.reference_type == ReferenceType.ACT_FOR
        assert ref.target_document_identifier == "2182-НП/И"

    def test_reference_immutable(self):
        rev = DocumentRevision(document_id="d")
        p = Provenance(document_revision=rev)
        ref = DocumentReference(ReferenceType.REFERS_TO, "a", "b", provenance=p)
        with pytest.raises(Exception):
            ref.confidence = 0.5  # frozen


# ── Neutral Fact Extraction Tests ──

class TestNeutralFactExtraction:
    def _make_company(self, name: str) -> BusinessEntity:
        return BusinessEntity(EntityType.COMPANY, name)

    def test_document_has_party(self):
        e = self._make_company("Шульгина")
        facts = FactExtractor().extract(
            entities=[e], identifiers=[], document_id="d",
            document_role="sale_contract", semantic_type="contract",
        )
        assert any(f.fact_type == FactType.DOCUMENT_HAS_PARTY for f in facts)

    def test_document_has_property(self):
        prop = BusinessEntity(EntityType.PROPERTY, "78:10:0005522:3018")
        facts = FactExtractor().extract(
            entities=[prop], identifiers=[], document_id="d",
            document_role="sale_contract", semantic_type="contract",
        )
        assert any(f.fact_type == FactType.DOCUMENT_HAS_PROPERTY for f in facts)

    def test_document_has_amount(self):
        facts = FactExtractor().extract(
            entities=[], identifiers=[], document_id="d",
            document_role="payment_order", semantic_type="payment_order",
            amounts=[1500000],
        )
        assert any(f.fact_type == FactType.DOCUMENT_HAS_AMOUNT for f in facts)

    def test_document_has_date(self):
        facts = FactExtractor().extract(
            entities=[], identifiers=[], document_id="d",
            document_role="contract", semantic_type="contract",
            contract_date=date(2026, 5, 26),
        )
        assert any(f.fact_type == FactType.DOCUMENT_HAS_DATE for f in facts)

    def test_document_has_role(self):
        facts = FactExtractor().extract(
            entities=[], identifiers=[], document_id="d",
            document_role="sale_contract", semantic_type="contract",
        )
        assert any(f.fact_type == FactType.DOCUMENT_HAS_ROLE for f in facts)

    def test_no_business_inference(self):
        """FactExtractor must NOT produce SELLS, OWNS, or other business interpretations."""
        seller = self._make_company("A")
        buyer = self._make_company("B")
        facts = FactExtractor().extract(
            entities=[seller, buyer], identifiers=[], document_id="d",
            document_role="sale_contract", semantic_type="contract",
        )
        business_facts = {"sells", "buys", "owns", "leases", "landlord", "tenant", 
                          "seller", "buyer", "customer", "supplier", "broker"}
        # All facts should be neutral DOCUMENT_HAS_* types
        for f in facts:
            assert f.fact_type.value not in business_facts
            assert f.fact_type.value.startswith("document_has_")

    def test_extraction_context_with_references(self):
        ctx = ExtractionContext(
            document_id="doc-1",
            entities=[BusinessEntity(EntityType.DOCUMENT, "2182-НП")],
            document_references=[
                DocumentReference(
                    ReferenceType.ACT_FOR, "doc-1", "2182-НП/И",
                    provenance=Provenance(document_revision=DocumentRevision(document_id="doc-1")),
                )
            ],
        )
        assert len(ctx.document_references) == 1
        assert ctx.document_references[0].reference_type == ReferenceType.ACT_FOR


# ── Entity Extraction Tests ──

class TestEntityExtraction:
    def test_extract_document_entity(self):
        """Contract number should create DOCUMENT entity, not AGREEMENT."""
        entities, _ = EntityExtractor().extract(
            ocr_entities={},
            raw_text="ДОГОВОР №2182-НП/И от 26.05.2026",
            document_id="doc-1",
        )
        doc_entities = [e for e in entities if e.entity_type == EntityType.DOCUMENT]
        assert len(doc_entities) >= 1
        assert any(e.display_name == "2182-НП" for e in doc_entities)

    def test_no_agreement_entity_created(self):
        """EntityExtractor must NOT create AGREEMENT entities."""
        entities, _ = EntityExtractor().extract(
            ocr_entities={},
            raw_text="ДОГОВОР №2182-НП/И",
            document_id="doc-1",
        )
        assert not any(e.entity_type == EntityType.AGREEMENT for e in entities)


# ── Full Pipeline Integration ──

class TestIntegration:
    def test_full_dkp_pipeline_neutral(self):
        ocr_entities = {
            "company": ["ИП Шульгина"],
            "vat_number": ["780527855675"],
            "amount": [5000000],
        }
        raw_text = (
            "ДОГОВОР №2182-НП/И купли-продажи нежилого помещения\n"
            "Кадастровый номер: 78:10:0005522:3018\n"
            "ИНН 780527855675"
        )

        # Extract
        extractor = EntityExtractor()
        raw_entities, raw_identifiers = extractor.extract(
            ocr_entities=ocr_entities, raw_text=raw_text, document_id="dkp-1",
            company_names=["ИП Шульгина"], vat_numbers=["780527855675"],
        )

        # Resolve
        resolver = EntityResolver()
        resolved = []
        for e in raw_entities:
            idfs = [idf for idf in raw_identifiers if idf.entity_id == e.id]
            matched, _ = resolver.resolve(idfs, entity_type=e.entity_type, display_name=e.display_name)
            if matched not in resolved:
                resolved.append(matched)

        # Extract facts
        facts = FactExtractor().extract(
            entities=resolved, identifiers=raw_identifiers, document_id="dkp-1",
            document_role="sale_contract", semantic_type="contract",
            ocr_entities=ocr_entities, amounts=[5000000], raw_text=raw_text,
        )

        # Build context
        ctx = ExtractionContext(
            document_id="dkp-1", entities=resolved, identifiers=raw_identifiers, facts=facts,
        )

        # Assertions
        assert any(e.entity_type == EntityType.DOCUMENT for e in ctx.entities)
        assert any(e.entity_type == EntityType.PROPERTY for e in ctx.entities)
        assert any(f.fact_type == FactType.DOCUMENT_HAS_PARTY for f in ctx.facts)
        assert any(f.fact_type == FactType.DOCUMENT_HAS_PROPERTY for f in ctx.facts)
        assert any(f.fact_type == FactType.DOCUMENT_HAS_AMOUNT for f in ctx.facts)

        # Must NOT contain business facts
        forbidden = {"sells", "buys", "owns", "leases", "landlord", "tenant", 
                     "seller", "buyer", "customer", "supplier", "broker"}
        for f in ctx.facts:
            assert f.fact_type.value not in forbidden
