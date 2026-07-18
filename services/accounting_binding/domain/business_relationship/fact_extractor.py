"""
FactExtractor v2.0.1a — neutral observations only.

Extracts ONLY what is actually found in the document.
NO business interpretation (SELLS, OWNS, BUYER, SELLER → v2.0.2).

Uses FactBuilder as the sole construction mechanism.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.fact import BusinessFact


class FactExtractor:
    """Extracts neutral observation facts. NO business inference."""

    def extract(
        self,
        entities: list[BusinessEntity],
        identifiers: list[EntityIdentifier],
        document_id: str,
        document_role: str,
        semantic_type: str,
        ocr_entities: dict | None = None,
        amounts: list | None = None,
        raw_text: str = "",
        contract_date: date | None = None,
    ) -> list[BusinessFact]:
        facts: list[BusinessFact] = []
        rev = DocumentRevision(document_id=document_id, created_by="ocr_v1.1+semantic_v1.5")
        prov = Provenance(document_revision=rev, extraction_method="semantic")

        # Helper: get entity IDs of a specific type
        def ids_by_type(entity_type: EntityType) -> list[str]:
            return [e.id for e in entities if e.entity_type == entity_type]

        # 1. DOCUMENT_HAS_PARTY — every company/person entity is a party
        for e in entities:
            if e.entity_type in (EntityType.COMPANY, EntityType.PERSON, EntityType.GOVERNMENT, EntityType.BANK):
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_PARTY,
                    subject_entity_id=e.id,
                    provenance=prov,
                    id=FactId.generate(),
                    object_entity_id=document_id,
                    confidence=FactConfidence(value=0.80),
                ))

        # 2. DOCUMENT_HAS_PROPERTY — if property entity detected
        for e in entities:
            if e.entity_type == EntityType.PROPERTY:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_PROPERTY,
                    subject_entity_id=e.id,
                    provenance=prov,
                    id=FactId.generate(),
                    object_entity_id=document_id,
                    confidence=FactConfidence(value=0.75),
                ))

        # 3. DOCUMENT_HAS_IDENTIFIER — INN, OGRN, etc.
        for idf in identifiers:
            if idf.identifier_type in (IdentifierType.INN, IdentifierType.OGRN):
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_IDENTIFIER,
                    subject_entity_id=idf.entity_id,
                    provenance=prov,
                    id=FactId.generate(),
                    value=FactValue.from_str(f"{idf.identifier_type.value}:{idf.normalized_value}"),
                    confidence=FactConfidence(value=idf.confidence),
                ))

        # 4. DOCUMENT_HAS_SIGNATURE — parties with INN are likely signatories
        inn_entities = set()
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.INN:
                inn_entities.add(idf.entity_id)
        for entity_id in inn_entities:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_SIGNATURE,
                subject_entity_id=entity_id,
                provenance=prov,
                id=FactId.generate(),
                object_entity_id=document_id,
                confidence=FactConfidence(value=0.70),
            ))

        # 5. DOCUMENT_HAS_AMOUNT
        total = Decimal("0")
        if amounts:
            for a in amounts:
                try:
                    total += Decimal(str(a))
                except Exception:
                    pass
        elif ocr_entities:
            amts = ocr_entities.get("amount", []) if isinstance(ocr_entities, dict) else []
            for a in amts:
                try:
                    total += Decimal(str(a))
                except Exception:
                    pass
        if total > 0:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_AMOUNT,
                subject_entity_id=document_id,
                provenance=prov,
                id=FactId.generate(),
                value=FactValue.from_decimal(total),
                confidence=FactConfidence(value=0.90),
            ))

        # 6. DOCUMENT_HAS_DATE
        if contract_date:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_DATE,
                subject_entity_id=document_id,
                provenance=prov,
                id=FactId.generate(),
                value=FactValue.from_date(contract_date),
                confidence=FactConfidence(value=0.85),
            ))

        # 7. DOCUMENT_HAS_ROLE — document has a business role
        if document_role and document_role != "unknown":
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_ROLE,
                subject_entity_id=document_id,
                provenance=prov,
                id=FactId.generate(),
                value=FactValue.from_str(document_role),
                confidence=FactConfidence(value=0.80),
            ))

        # 8. DOCUMENT_HAS_ADDRESS — if address found in identifiers
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.ADDRESS:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_ADDRESS,
                    subject_entity_id=idf.entity_id,
                    provenance=prov,
                    id=FactId.generate(),
                    value=FactValue.from_str(idf.normalized_value),
                    confidence=FactConfidence(value=idf.confidence),
                ))

        # 9. DOCUMENT_HAS_CONTRACT_NUMBER
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.CONTRACT_NUMBER:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_CONTRACT_NUMBER,
                    subject_entity_id=idf.entity_id,
                    provenance=prov,
                    id=FactId.generate(),
                    value=FactValue.from_str(idf.normalized_value),
                    confidence=FactConfidence(value=idf.confidence),
                ))

        return facts
