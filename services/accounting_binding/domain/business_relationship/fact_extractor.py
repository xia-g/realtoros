"""
FactExtractor v2.0.1a — neutral observations only.

Extracts ONLY what is actually found in the document.
NO business interpretation (SELLS, OWNS, BUYER, SELLER → v2.0.2).

Facts:
  DOCUMENT_HAS_PARTY     — document mentions a party
  DOCUMENT_HAS_PROPERTY  — document references property
  DOCUMENT_HAS_AMOUNT    — document has a monetary amount
  DOCUMENT_HAS_DATE      — document has a date
  DOCUMENT_HAS_IDENTIFIER — document has an identifier (INN)
  DOCUMENT_HAS_SIGNATURE  — document is signed by a party
  DOCUMENT_HAS_ROLE       — document has a business role
  DOCUMENT_HAS_ADDRESS    — document contains an address
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.provenance import Provenance, DocumentRevision
from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_types import EntityType, IdentifierType


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
                    subject_entity_id=document_id,
                    object_entity_id=e.id,
                    provenance=prov,
                    confidence=0.80,
                ))

        # 2. DOCUMENT_HAS_PROPERTY — if property entity detected
        for e in entities:
            if e.entity_type == EntityType.PROPERTY:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_PROPERTY,
                    subject_entity_id=document_id,
                    object_entity_id=e.id,
                    provenance=prov,
                    confidence=0.75,
                ))

        # 3. DOCUMENT_HAS_IDENTIFIER — INN, OGRN, etc.
        for idf in identifiers:
            if idf.identifier_type in (IdentifierType.INN, IdentifierType.OGRN):
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_IDENTIFIER,
                    subject_entity_id=document_id,
                    value=f"{idf.identifier_type.value}:{idf.normalized_value}",
                    provenance=prov,
                    confidence=idf.confidence,
                ))

        # 4. DOCUMENT_HAS_SIGNATURE — parties with INN are likely signatories
        inn_entities = set()
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.INN:
                inn_entities.add(idf.entity_id)
        for entity_id in inn_entities:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_SIGNATURE,
                subject_entity_id=document_id,
                object_entity_id=entity_id,
                provenance=prov,
                confidence=0.70,
            ))

        # 5. DOCUMENT_HAS_AMOUNT
        total = Decimal("0")
        if amounts:
            for a in amounts:
                try: total += Decimal(str(a))
                except: pass
        elif ocr_entities:
            amts = ocr_entities.get("amount", []) if isinstance(ocr_entities, dict) else []
            for a in amts:
                try: total += Decimal(str(a))
                except: pass
        if total > 0:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_AMOUNT,
                subject_entity_id=document_id,
                value=str(total),
                provenance=prov,
                confidence=0.90,
            ))

        # 6. DOCUMENT_HAS_DATE
        if contract_date:
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_DATE,
                subject_entity_id=document_id,
                value=str(contract_date),
                provenance=prov,
                confidence=0.85,
            ))

        # 7. DOCUMENT_HAS_ROLE — document has a business role
        if document_role and document_role != "unknown":
            facts.append(BusinessFact(
                fact_type=FactType.DOCUMENT_HAS_ROLE,
                subject_entity_id=document_id,
                value=document_role,
                provenance=prov,
                confidence=0.80,
            ))

        # 8. DOCUMENT_HAS_ADDRESS — if address found in identifiers
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.ADDRESS:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_ADDRESS,
                    subject_entity_id=document_id,
                    value=idf.normalized_value,
                    provenance=prov,
                    confidence=idf.confidence,
                ))

        # 9. DOCUMENT_HAS_CONTRACT_NUMBER
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.CONTRACT_NUMBER:
                facts.append(BusinessFact(
                    fact_type=FactType.DOCUMENT_HAS_CONTRACT_NUMBER,
                    subject_entity_id=document_id,
                    value=idf.normalized_value,
                    provenance=prov,
                    confidence=idf.confidence,
                ))

        return facts
