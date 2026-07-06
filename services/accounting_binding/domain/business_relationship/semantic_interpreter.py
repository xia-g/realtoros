"""
SemanticInterpreter — interprets neutral facts into business semantics.

Input:  document_role, semantic_classification, neutral facts, raw_text
Output: agreement_type, participant roles, transaction semantics

NOT persistent. NO DB writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_types import EntityType


# Map document_role → AgreementType
ROLE_TO_AGREEMENT: dict[str, AgreementType] = {
    "sale_contract": AgreementType.SALE,
    "transfer_act": AgreementType.SALE,       # акт приема-передачи → часть сделки купли-продажи
    "payment_order": AgreementType.SALE,       # платёжное поручение → часть сделки
    "invoice": AgreementType.OFFER,            # счёт → оферта
    "receipt": AgreementType.SALE,             # чек → оплата по сделке
    "egrn_extract": AgreementType.PURCHASE,    # выписка ЕГРН → покупка
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


@dataclass
class SemanticInterpretation:
    """Результат интерпретации нейтральных фактов."""
    agreement_type: AgreementType = AgreementType.UNKNOWN
    participant_roles: list[tuple[str, ParticipantRole]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: list[str] = field(default_factory=list)


class SemanticInterpreter:
    """Интерпретирует нейтральные факты в бизнес-семантику."""

    def interpret(
        self,
        document_role: str,
        semantic_classification: str,
        facts: list[BusinessFact],
        entities: list[BusinessEntity],
        raw_text: str = "",
    ) -> SemanticInterpretation:
        """Интерпретировать документ как соглашение."""
        reasoning: list[str] = []

        # 1. Determine agreement type from document_role
        agreement_type = ROLE_TO_AGREEMENT.get(document_role, AgreementType.UNKNOWN)

        # Fallback: use semantic classification
        if agreement_type == AgreementType.UNKNOWN:
            sem_lower = semantic_classification.lower()
            if "contract" in sem_lower or "договор" in sem_lower:
                agreement_type = AgreementType.SALE  # default
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
        reasoning.append(f"document_role='{document_role}' → type={agreement_type.value}")

        # 2. Assign participant roles
        party_entities = [e for e in entities 
                          if e.entity_type in (EntityType.COMPANY, EntityType.PERSON, EntityType.GOVERNMENT)]
        participant_roles: list[tuple[str, ParticipantRole]] = []

        role_map = AGREEMENT_PARTICIPANT_MAP.get(agreement_type, {})

        for idx, entity in enumerate(party_entities):
            if idx in dict(role_map):
                role = dict(role_map)[idx]
            else:
                role = ParticipantRole.UNKNOWN
            participant_roles.append((entity.id, role))
            reasoning.append(f"entity[{idx}]='{entity.display_name}' → role={role.value}")

        # 3. Confidence: based on agreement type certainty
        confidence = 0.85 if agreement_type != AgreementType.UNKNOWN else 0.30

        return SemanticInterpretation(
            agreement_type=agreement_type,
            participant_roles=participant_roles,
            confidence=confidence,
            reasoning=reasoning,
        )
