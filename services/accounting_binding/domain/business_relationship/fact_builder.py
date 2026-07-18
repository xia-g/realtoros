"""
FactBuilder — единственный способ создания BusinessFact.

Не содержит бизнес-логики.
Не делает выводов.
Не создаёт Knowledge.
Только конструирует корректный immutable BusinessFact.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact_id import FactId
from domain.business_relationship.fact_value import FactValue
from domain.business_relationship.fact_confidence import FactConfidence
from domain.business_relationship.fact_source import FactSource
from domain.business_relationship.fact_evidence import FactEvidence
from domain.business_relationship.provenance import Provenance, DocumentRevision


class FactBuilder:
    """Конструктор BusinessFact.

    Единственный удобный способ создания факта.
    NO business logic. NO inference. Only construction.
    """

    @staticmethod
    def build(
        fact_type: FactType,
        subject_entity_id: str,
        document_id: str,
        object_entity_id: str | None = None,
        value: FactValue | None = None,
        confidence: FactConfidence | None = None,
        fact_id: FactId | None = None,
        revision: int = 1,
        extraction_method: str = "regex",
    ) -> BusinessFact:
        """Создать BusinessFact с минимальным набором полей."""
        rev = DocumentRevision(document_id=document_id, revision=revision)
        prov = Provenance(document_revision=rev, extraction_method=extraction_method)

        return BusinessFact(
            fact_type=fact_type,
            subject_entity_id=subject_entity_id,
            provenance=prov,
            id=fact_id or FactId.generate(),
            object_entity_id=object_entity_id,
            value=value,
            confidence=confidence or FactConfidence.medium(),
        )

    @staticmethod
    def document_has_party(
        document_id: str,
        entity_id: str,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_PARTY,
            subject_entity_id=entity_id,
            document_id=document_id,
            confidence=confidence or FactConfidence.medium(),
        )

    @staticmethod
    def document_has_property(
        document_id: str,
        property_id: str,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_PROPERTY,
            subject_entity_id=property_id,
            document_id=document_id,
            confidence=confidence or FactConfidence.medium(),
        )

    @staticmethod
    def document_has_amount(
        document_id: str,
        amount: Decimal,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_AMOUNT,
            subject_entity_id=document_id,
            document_id=document_id,
            value=FactValue.from_decimal(amount),
            confidence=confidence or FactConfidence.high(),
        )

    @staticmethod
    def document_has_date(
        document_id: str,
        fact_date: date,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_DATE,
            subject_entity_id=document_id,
            document_id=document_id,
            value=FactValue.from_date(fact_date),
            confidence=confidence or FactConfidence.high(),
        )

    @staticmethod
    def document_has_identifier(
        document_id: str,
        identifier_value: str,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_IDENTIFIER,
            subject_entity_id=document_id,
            document_id=document_id,
            value=FactValue.from_str(identifier_value),
            confidence=confidence or FactConfidence.medium(),
        )

    @staticmethod
    def document_has_role(
        document_id: str,
        role: str,
        confidence: FactConfidence | None = None,
    ) -> BusinessFact:
        return FactBuilder.build(
            fact_type=FactType.DOCUMENT_HAS_ROLE,
            subject_entity_id=document_id,
            document_id=document_id,
            value=FactValue.from_str(role),
            confidence=confidence or FactConfidence.medium(),
        )
