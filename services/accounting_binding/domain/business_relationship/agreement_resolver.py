"""
AgreementResolver — orchestrate interpretation + matching.

1. SemanticInterpreter → determine agreement type + roles
2. AgreementMatcher → find existing or create new
3. Build AgreementParticipants from interpreted roles
4. Return AgreementContext

All in-memory. NO DB writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.business_relationship.agreement import Agreement, KnowledgeState
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.semantic_interpreter import SemanticInterpreter, SemanticInterpretation
from domain.business_relationship.agreement_matcher import AgreementMatcher
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.document_reference import DocumentReference


@dataclass
class AgreementContext:
    """Результат разрешения соглашения."""
    agreement: Agreement | None = None
    participants: list[AgreementParticipant] = field(default_factory=list)
    supporting_document_ids: list[str] = field(default_factory=list)
    document_references: list[DocumentReference] = field(default_factory=list)
    confidence: float = 0.0
    resolution_evidence: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        ag = self.agreement
        if not ag:
            return "AgreementContext(empty)"
        roles = ", ".join(f"{p.participant_role.value}" for p in self.participants[:3])
        return f"AgreementContext({ag.summary}, roles=[{roles}], conf={self.confidence:.2f})"


class AgreementResolver:
    """Оркестратор разрешения соглашений."""

    def __init__(
        self,
        matcher: AgreementMatcher | None = None,
        interpreter: SemanticInterpreter | None = None,
    ):
        self._matcher = matcher or AgreementMatcher()
        self._interpreter = interpreter or SemanticInterpreter()

    def resolve(
        self,
        document_role: str,
        semantic_type: str,
        facts: list[BusinessFact],
        entities: list[BusinessEntity],
        document_id: str,
        document_references: list[DocumentReference] | None = None,
        raw_text: str = "",
    ) -> AgreementContext:
        """Разрешить соглашение из контекста извлечения."""
        evidence: list[str] = []

        # 1. Semantic interpretation
        interpretation = self._interpreter.interpret(
            document_role=document_role,
            semantic_classification=semantic_type,
            facts=facts,
            entities=entities,
            raw_text=raw_text,
        )
        evidence.extend(interpretation.reasoning)

        # 2. Find contract number from facts
        contract_number = ""
        for f in facts:
            if f.fact_type == FactType.DOCUMENT_HAS_CONTRACT_NUMBER and f.value:
                contract_number = f.value

        # Also check entities for DOCUMENT type
        doc_entities = [e for e in entities if e.entity_type.value == "document"]
        if not contract_number and doc_entities:
            contract_number = doc_entities[0].display_name

        # 3. Find existing agreement
        existing = self._matcher.find_or_none(
            number=contract_number,
            document_references=document_references,
        )

        if existing:
            evidence.append(f"Found existing agreement: {existing.summary}")
            # Add supporting docs
            if document_id not in existing.supporting_document_ids:
                existing.supporting_document_ids.append(document_id)

            # Reuse existing participants
            return AgreementContext(
                agreement=existing,
                participants=[],  # will be populated per-agreement
                supporting_document_ids=existing.supporting_document_ids,
                document_references=document_references or [],
                confidence=max(0.90, interpretation.confidence),
                resolution_evidence=evidence,
            )

        # 4. Create new agreement
        # Extract amount from facts
        amount = Decimal("0")
        for f in facts:
            if f.fact_type == FactType.DOCUMENT_HAS_AMOUNT and f.value:
                try: amount = Decimal(f.value)
                except: pass

        agreement = Agreement(
            agreement_type=interpretation.agreement_type,
            number=contract_number,
            amount=amount,
            document_entity_id=doc_entities[0].id if doc_entities else "",
            confidence=interpretation.confidence,
        )
        evidence.append(f"Created new agreement: {agreement.summary}")

        # 5. Create participants
        participants = []
        for entity_id, role in interpretation.participant_roles:
            participants.append(AgreementParticipant(
                agreement_id=agreement.id,
                entity_id=entity_id,
                participant_role=role,
                confidence=interpretation.confidence,
            ))
        evidence.append(f"Created {len(participants)} participants")

        # 6. Register
        self._matcher.register(agreement)

        return AgreementContext(
            agreement=agreement,
            participants=participants,
            supporting_document_ids=[document_id],
            document_references=document_references or [],
            confidence=interpretation.confidence,
            resolution_evidence=evidence,
        )
