"""
SemanticInterpreter — interprets neutral facts into business semantics.

Input:  document_role, semantic_classification, neutral facts, raw_text
Output: AgreementCandidate (immutable)

Deterministic. Stateless. Side-effect free.
NO knowledge of Agreement Repository, Graph, Identity, Projection, Query.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.agreement_candidate import AgreementCandidate
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType


# Map document_role → AgreementType
ROLE_TO_AGREEMENT: dict[str, AgreementType] = {
    "sale_contract": AgreementType.SALE,
    "transfer_act": AgreementType.SALE,
    "payment_order": AgreementType.SALE,
    "invoice": AgreementType.OFFER,
    "receipt": AgreementType.SALE,
    "egrn_extract": AgreementType.PURCHASE,
    "passport": AgreementType.PURCHASE,
    "certificate": AgreementType.PURCHASE,
    "lease": AgreementType.LEASE,
    "amendment": AgreementType.FRAMEWORK,
    "service": AgreementType.SERVICE,
    "agency": AgreementType.AGENCY,
    "commission": AgreementType.COMMISSION,
    "loan": AgreementType.LOAN,
    "municipal_contract": AgreementType.PURCHASE,
    "other_contract": AgreementType.LEASE,
    "unknown": AgreementType.UNKNOWN,
}

# For known agreement types, determine roles
AGREEMENT_PARTICIPANT_MAP: dict[AgreementType, list[tuple[int, ParticipantRole]]] = {
    AgreementType.SALE: [(0, ParticipantRole.SELLER), (1, ParticipantRole.BUYER)],
    AgreementType.PURCHASE: [(0, ParticipantRole.BUYER), (1, ParticipantRole.SELLER)],
    AgreementType.LEASE: [(0, ParticipantRole.LANDLORD), (1, ParticipantRole.TENANT)],
    AgreementType.SERVICE: [(0, ParticipantRole.CONTRACTOR), (1, ParticipantRole.CLIENT)],
    AgreementType.AGENCY: [(0, ParticipantRole.AGENT), (1, ParticipantRole.PRINCIPAL)],
    AgreementType.COMMISSION: [(0, ParticipantRole.AGENT), (1, ParticipantRole.PRINCIPAL)],
    AgreementType.FRAMEWORK: [(0, ParticipantRole.SUPPLIER), (1, ParticipantRole.CUSTOMER)],
    AgreementType.LOAN: [(0, ParticipantRole.SUPPLIER), (1, ParticipantRole.CUSTOMER)],
    AgreementType.OFFER: [(0, ParticipantRole.SUPPLIER), (1, ParticipantRole.CUSTOMER)],
}


class SemanticInterpreter:
    """Интерпретирует нейтральные факты в бизнес-семантику.

    Deterministic. Stateless. Side-effect free.
    """

    @staticmethod
    def interpret(
        document_role: str,
        semantic_classification: str,
        facts: list[BusinessFact],
        entities: list[BusinessEntity],
        raw_text: str = "",
    ) -> AgreementCandidate:
        """Интерпретировать факты как соглашение. Возвращает AgreementCandidate."""
        evidence: list[str] = []

        # 1. Determine agreement type from document_role
        agreement_type = ROLE_TO_AGREEMENT.get(document_role, AgreementType.UNKNOWN)

        # Fallback: use semantic classification
        if agreement_type == AgreementType.UNKNOWN:
            sem_lower = semantic_classification.lower()
            if "contract" in sem_lower or "договор" in sem_lower:
                agreement_type = AgreementType.SALE
            elif "invoice" in sem_lower or "счёт" in sem_lower:
                agreement_type = AgreementType.OFFER
            elif "receipt" in sem_lower or "чек" in sem_lower:
                agreement_type = AgreementType.OFFER
            elif "act" in sem_lower or "акт" in sem_lower:
                agreement_type = AgreementType.SERVICE
            elif "payment" in sem_lower or "платёж" in sem_lower:
                agreement_type = AgreementType.PURCHASE
            elif "property" in sem_lower or "недвижим" in sem_lower:
                agreement_type = AgreementType.PURCHASE

        # 2. Assign participant roles
        party_entities = [e for e in entities
                          if e.entity_type in (EntityType.COMPANY, EntityType.PERSON, EntityType.GOVERNMENT)]
        participant_roles: list[tuple[str, ParticipantRole]] = []

        role_map = AGREEMENT_PARTICIPANT_MAP.get(agreement_type, {})

        for idx, entity in enumerate(party_entities):
            role = dict(role_map).get(idx, ParticipantRole.UNKNOWN)
            participant_roles.append((entity.id, role))

        # 3. Extract contract number from facts
        contract_number = ""
        for f in facts:
            if f.fact_type == FactType.DOCUMENT_HAS_CONTRACT_NUMBER and f.value:
                contract_number = str(f.value)

        # Extract amount
        amount = Decimal("0")
        for f in facts:
            if f.fact_type == FactType.DOCUMENT_HAS_AMOUNT and f.value:
                try:
                    amount = Decimal(str(f.value))
                except Exception:
                    pass

        # Extract supporting document IDs
        doc_ids: set[str] = set()
        for f in facts:
            doc_ids.add(f.document_id)
        doc_entities = [e for e in entities if e.entity_type.value == "document"]
        if not contract_number and doc_entities:
            contract_number = doc_entities[0].display_name

        # Confidence
        confidence = 0.85 if agreement_type != AgreementType.UNKNOWN else 0.30

        return AgreementCandidate(
            agreement_type=agreement_type,
            contract_number=contract_number,
            amount=amount,
            participant_roles=tuple(participant_roles),
            supporting_document_ids=tuple(doc_ids),
            confidence=confidence,
            source_facts=tuple(facts),
        )
