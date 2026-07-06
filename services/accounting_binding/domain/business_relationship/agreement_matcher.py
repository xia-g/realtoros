"""
AgreementMatcher — find existing agreements from context.

Uses: contract number, date, participants, property, amount.
NO SQL. Works with in-memory models.
"""
from __future__ import annotations

from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.document_reference import DocumentReference, ReferenceType


class AgreementMatcher:
    """Поиск существующих соглашений."""

    def __init__(self, existing_agreements: list[Agreement] | None = None):
        self._agreements: dict[str, Agreement] = {}
        self._by_number: dict[str, str] = {}  # number → agreement_id
        if existing_agreements:
            for a in existing_agreements:
                self._agreements[a.id] = a
                if a.number:
                    self._by_number[a.number] = a.id

    def find_by_number(self, number: str) -> Agreement | None:
        if not number:
            return None
        aid = self._by_number.get(number)
        return self._agreements.get(aid) if aid else None

    def find_or_none(
        self,
        number: str = "",
        document_references: list[DocumentReference] | None = None,
    ) -> Agreement | None:
        """Find existing agreement by any matching criteria."""
        # 1. By contract number (most reliable)
        if number:
            norm = number.strip().upper()
            for aid, a in self._agreements.items():
                if a.number and a.number.strip().upper() == norm:
                    return a

        # 2. By document reference
        if document_references:
            for ref in document_references:
                if ref.reference_type in (ReferenceType.ACT_FOR, ReferenceType.REFERS_TO, 
                                          ReferenceType.APPENDIX_TO, ReferenceType.EXECUTES):
                    # The target identifier might match an agreement number
                    norm_ref = ref.target_document_identifier.strip().upper()
                    for a in self._agreements.values():
                        if a.number and a.number.strip().upper() == norm_ref:
                            return a

        return None

    def register(self, agreement: Agreement):
        self._agreements[agreement.id] = agreement
        if agreement.number:
            self._by_number[agreement.number] = agreement.id

    @property
    def agreements(self) -> list[Agreement]:
        return list(self._agreements.values())
