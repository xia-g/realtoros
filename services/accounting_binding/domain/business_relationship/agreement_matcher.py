"""
AgreementMatcher — match candidates against existing agreements.

Decision only. NO mutation. NO side effects.
Deterministic: same candidate + same existing → same decision.
"""
from __future__ import annotations

from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_candidate import AgreementCandidate
from domain.business_relationship.agreement_match_result import (
    AgreementMatchResult, MatchDecision,
)


class AgreementMatcher:
    """Сопоставляет кандидата с существующими соглашениями.

    Stateless. Decision only. NO mutation of agreements.
    """

    @staticmethod
    def match(
        candidate: AgreementCandidate,
        existing_agreements: list[Agreement],
    ) -> AgreementMatchResult:
        """Сопоставить кандидата с существующими соглашениями.

        Returns MatchDecision:
          - MATCHED: exact match found
          - NO_MATCH: new agreement needed
          - AMBIGUOUS: multiple candidates match
          - CONFLICT: contradictory information
        """
        if not candidate.contract_number:
            return AgreementMatchResult(
                decision=MatchDecision.NO_MATCH,
                candidate=candidate,
                reason="No contract number to match against",
            )

        norm_candidate = candidate.contract_number.strip().upper()

        # Find all agreements with matching number
        matches: list[Agreement] = []
        for a in existing_agreements:
            if a.number and a.number.strip().upper() == norm_candidate:
                matches.append(a)

        if len(matches) == 1:
            return AgreementMatchResult(
                decision=MatchDecision.MATCHED,
                candidate=candidate,
                matched_agreement=matches[0],
                reason=f"Exact match by contract number '{candidate.contract_number}'",
                confidence=max(0.95, candidate.confidence),
            )

        if len(matches) > 1:
            return AgreementMatchResult(
                decision=MatchDecision.AMBIGUOUS,
                candidate=candidate,
                reason=f"Multiple agreements ({len(matches)}) match number '{candidate.contract_number}'",
            )

        # Check by document references
        doc_ids = candidate.supporting_document_ids
        for a in existing_agreements:
            if a.metadata.source_document_id in doc_ids:
                return AgreementMatchResult(
                    decision=MatchDecision.MATCHED,
                    candidate=candidate,
                    matched_agreement=a,
                    reason=f"Matched by source document '{a.metadata.source_document_id}'",
                    confidence=0.85,
                )

        return AgreementMatchResult(
            decision=MatchDecision.NO_MATCH,
            candidate=candidate,
            reason=f"No existing agreement matches '{candidate.contract_number}'",
        )

    @staticmethod
    def find_exact(
        existing_agreements: list[Agreement],
        *,
        number: str = "",
        document_id: str = "",
    ) -> Agreement | None:
        """Find exact agreement by number or document ID. Pure query."""
        if number:
            norm = number.strip().upper()
            for a in existing_agreements:
                if a.number and a.number.strip().upper() == norm:
                    return a
        if document_id:
            for a in existing_agreements:
                if a.metadata.source_document_id == document_id:
                    return a
        return None
