"""
AgreementResolver — coordinator of agreement resolution.

Pipeline: BusinessFacts → AgreementInterpreter → AgreementMatcher → Agreement

Deterministic. Stateless. Side-effect free.
NO IO. NO DB. NO Infrastructure.
NO Knowledge. NO Graph. NO Identity. NO Projection. NO Query.

Same facts → same Agreement every time.
"""
from __future__ import annotations

from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_metadata import AgreementMetadata
from domain.business_relationship.agreement_candidate import AgreementCandidate
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.agreement_match_result import AgreementMatchResult, MatchDecision
from domain.business_relationship.agreement_resolution_result import (
    AgreementResolutionResult, AgreementResolutionReport,
)
from domain.business_relationship.semantic_interpreter import SemanticInterpreter
from domain.business_relationship.agreement_matcher import AgreementMatcher


class AgreementResolver:
    """Оркестратор разрешения соглашений.

    Interpreter → Matcher → Agreement.
    No heuristics. All rules explicit. Deterministic.
    """

    def __init__(
        self,
        interpreter: SemanticInterpreter | None = None,
    ):
        self._interpreter = interpreter or SemanticInterpreter()
        self._matcher = AgreementMatcher()

    def resolve(
        self,
        facts: list[BusinessFact],
        entities: list[BusinessEntity],
        document_role: str,
        semantic_classification: str,
        existing_agreements: list[Agreement] | None = None,
    ) -> AgreementResolutionResult:
        """Разрешить соглашение из нейтральных фактов.

        Args:
            facts: Neutral BusinessFacts extracted from document
            entities: Entities extracted from document
            document_role: Document role classification
            semantic_classification: Semantic type classification
            existing_agreements: Previously resolved agreements (for matching)

        Returns:
            AgreementResolutionResult with agreement, participants, evidence
        """
        evidence: list[str] = []

        # 1. Interpreter → candidate
        candidate = self._interpreter.interpret(
            document_role=document_role,
            semantic_classification=semantic_classification,
            facts=facts,
            entities=entities,
        )

        if not candidate.has_minimal_data:
            evidence.append("No viable agreement candidate from facts")
            return AgreementResolutionResult(
                candidate=candidate,
                evidence=tuple(evidence),
            )

        evidence.append(
            f"Interpretation: type={candidate.agreement_type.value}, "
            f"roles={candidate.participant_count}, "
            f"conf={candidate.confidence:.2f}"
        )

        # 2. Matcher → match decision
        existing = existing_agreements or []
        match_result = self._matcher.match(candidate, existing)
        evidence.append(f"Match: {match_result.decision.value} — {match_result.reason}")

        # 3. Build result based on match
        if match_result.decision == MatchDecision.MATCHED and match_result.matched_agreement:
            return AgreementResolutionResult(
                agreement=match_result.matched_agreement,
                participants=(),
                match_result=match_result,
                candidate=candidate,
                evidence=tuple(evidence),
            )

        if match_result.decision == MatchDecision.AMBIGUOUS:
            return AgreementResolutionResult(
                candidate=candidate,
                match_result=match_result,
                evidence=tuple(evidence),
            )

        # 4. NO_MATCH → create new Agreement
        agreement = Agreement(
            agreement_type=candidate.agreement_type,
            id=AgreementId.generate(),
            number=candidate.contract_number,
            amount=candidate.amount,
            metadata=AgreementMetadata(
                source_document_id=(
                    candidate.supporting_document_ids[0]
                    if candidate.supporting_document_ids else ""
                ),
                confidence=candidate.confidence,
            ),
        )

        participants = tuple(
            AgreementParticipant(
                agreement_id=agreement.id,
                entity_id=entity_id,
                participant_role=role,
                confidence=candidate.confidence,
            )
            for entity_id, role in candidate.participant_roles
        )

        evidence.append(
            f"Created: {agreement.summary}, participants={len(participants)}"
        )

        return AgreementResolutionResult(
            agreement=agreement,
            participants=participants,
            match_result=match_result,
            candidate=candidate,
            evidence=tuple(evidence),
        )
