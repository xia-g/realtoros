"""
IdentityResolver — превращает разные представления в канонические сущности.

1. Normalize identifiers from AgreementContext + ExtractionContext
2. Find matches among known canonical entities
3. Merge aliases + increase confidence
4. Create new canonical entities if no match found

All in-memory. NO DB writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId
from domain.business_relationship.canonical_property import CanonicalProperty
from domain.business_relationship.canonical_agreement import CanonicalAgreement
from domain.business_relationship.entity_alias import EntityAlias as Alias, AliasType
from domain.business_relationship.support_models import (
    MergeCandidate, MergeDecision, ConfidenceHistory,
)
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.agreement import Agreement
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.fact_types import FactType
from domain.business_relationship.fact import BusinessFact
from domain.business_relationship.document_reference import DocumentReference


@dataclass
class MasterDataContext:
    """Итог анализа — все канонические сущности."""
    canonical_entities: list[CanonicalEntity] = field(default_factory=list)
    canonical_properties: list[CanonicalProperty] = field(default_factory=list)
    canonical_agreements: list[CanonicalAgreement] = field(default_factory=list)
    merge_candidates: list[MergeCandidate] = field(default_factory=list)
    resolution_evidence: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        ce = len(self.canonical_entities)
        cp = len(self.canonical_properties)
        ca = len(self.canonical_agreements)
        mc = len(self.merge_candidates)
        return f"MasterData(entities={ce}, properties={cp}, agreements={ca}, merge_candidates={mc})"


class IdentityResolver:
    """Разрешает идентичность: разные представления → одна сущность."""

    def __init__(self):
        self._store: list[CanonicalEntity] = []
        self._properties: list[CanonicalProperty] = []
        self._agreements: list[CanonicalAgreement] = []

    def resolve(
        self,
        entities: list[BusinessEntity],
        identifiers: list[EntityIdentifier],
        agreement: Agreement | None,
        facts: list[BusinessFact],
        document_id: str,
    ) -> MasterDataContext:
        evidence: list[str] = []
        merge_candidates: list[MergeCandidate] = []

        # ── 1. Resolve entities ──
        canonical_entities: list[CanonicalEntity] = []
        for e in entities:
            entity_idfs = [idf for idf in identifiers if idf.entity_id == e.id]
            ce = self._resolve_entity(e, entity_idfs, document_id, evidence)
            canonical_entities.append(ce)

        # ── 2. Resolve properties ──
        canonical_props: list[CanonicalProperty] = []
        for e in entities:
            if e.entity_type != EntityType.PROPERTY:
                continue
            cp = self._resolve_property(e, identifiers, document_id, evidence)
            canonical_props.append(cp)

        # ── 3. Resolve agreements ──
        canonical_agreements: list[CanonicalAgreement] = []
        if agreement:
            ca = self._resolve_agreement(agreement, document_id, evidence)
            canonical_agreements.append(ca)

        # ── 4. Merge candidates ──
        merge_candidates = self._find_merge_candidates(canonical_entities)

        return MasterDataContext(
            canonical_entities=canonical_entities,
            canonical_properties=canonical_props,
            canonical_agreements=canonical_agreements,
            merge_candidates=merge_candidates,
            resolution_evidence=evidence,
        )

    def _resolve_entity(
        self, e: BusinessEntity,
        identifiers: list[EntityIdentifier],
        document_id: str,
        evidence: list[str],
    ) -> CanonicalEntity:
        """Разрешить одну бизнес-сущность."""
        nr = NormalizationService

        # Normalize identifiers
        display = e.display_name
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.INN:
                display = idf.value
            elif idf.identifier_type == IdentifierType.CONTRACT_NUMBER:
                pass  # not for display

        # Try to find existing canonical entity
        matched = self._find_canonical(identifiers)
        if matched:
            evidence.append(f"Matched existing canonical: {matched.display_name}")
            matched.add_alias(display, display, source_doc=document_id)
            matched.confirm(document_id)
            matched.updated_at = __import__("datetime").datetime.utcnow()
            return matched

        # Create new canonical entity
        ce = CanonicalEntity(entity_type=e.entity_type, display_name=display, id=CanonicalEntityId.generate())
        if identifiers:
            # Best identifier
            for idf in identifiers:
                if idf.identifier_type == IdentifierType.INN:
                    ce.primary_identifier = idf.value
                    break
            ce.identifiers = [idf.value for idf in identifiers]

        ce.confirm(document_id)
        self._store.append(ce)
        evidence.append(f"Created new canonical entity: {display}")
        return ce

    def _resolve_property(
        self, e: BusinessEntity,
        identifiers: list[EntityIdentifier],
        document_id: str,
        evidence: list[str],
    ) -> CanonicalProperty:
        """Разрешить объект недвижимости."""
        cadastral = ""
        address = ""
        for idf in identifiers:
            if idf.identifier_type == IdentifierType.CADASTRE:
                cadastral = idf.value
            if idf.identifier_type == IdentifierType.ADDRESS:
                address = idf.value

        # Check existing properties
        for cp in self._properties:
            if cadastral and cp.cadastral_number == cadastral:
                cp.confirm(document_id)
                evidence.append(f"Matched existing property: {cadastral}")
                return cp
            if address and cp.normalized_address == NormalizationService.normalize_address(address):
                cp.confirm(document_id)
                evidence.append(f"Matched property by address")
                return cp

        # New
        cp = CanonicalProperty(
            cadastral_number=cadastral,
            normalized_address=NormalizationService.normalize_address(address),
        )
        cp.confirm(document_id)
        self._properties.append(cp)
        evidence.append(f"Created new property: {cadastral or address[:30]}")
        return cp

    def _resolve_agreement(
        self, agreement: Agreement,
        document_id: str,
        evidence: list[str],
    ) -> CanonicalAgreement:
        """Разрешить соглашение."""
        for ca in self._agreements:
            if ca.number and ca.number == agreement.number:
                ca.confirm(document_id)
                evidence.append(f"Matched existing canonical agreement: {ca.number}")
                return ca

        ca = CanonicalAgreement(
            agreement_id=agreement.id,
            agreement_type=agreement.agreement_type,
            number=agreement.number,
            amount=agreement.amount or Decimal("0"),
        )
        ca.confirm(document_id)
        self._agreements.append(ca)
        evidence.append(f"Created canonical agreement: {ca.number or ca.id[:8]}")
        return ca

    def _find_canonical(self, identifiers: list[EntityIdentifier]) -> CanonicalEntity | None:
        """Найти существующую каноническую сущность по любому идентификатору."""
        norm_vals = {idf.value for idf in identifiers}
        for ce in self._store:
            ce_norms = set(ce.identifiers)
            if norm_vals & ce_norms:
                return ce
            # Also check aliases
            for alias in ce.aliases:
                if alias.value in norm_vals:
                    return ce
        return None

    def _find_merge_candidates(self, entities: list[CanonicalEntity]) -> list[MergeCandidate]:
        """Найти пары на объединение."""
        candidates = []
        for i, a in enumerate(entities):
            for b in entities[i+1:]:
                score = self._similarity(a, b)
                if score >= 95:
                    candidates.append(MergeCandidate(
                        left_entity_id=a.id,
                        right_entity_id=b.id,
                        similarity_score=score,
                        reasons=[f"display={a.display_name}↔{b.display_name}", f"score={score}"],
                    ))
        return candidates

    def _similarity(self, a: CanonicalEntity, b: CanonicalEntity) -> float:
        """Грубая оценка схожести двух сущностей."""
        if a.entity_type != b.entity_type:
            return 0.0
        # Same primary identifier = 100
        if a.primary_identifier and a.primary_identifier == b.primary_identifier:
            return 100.0
        # Same display name = 100
        if a.display_name.lower() == b.display_name.lower():
            return 100.0
        # Overlap in identifiers
        a_idents = set(a.identifiers)
        b_idents = set(b.identifiers)
        if a_idents and b_idents:
            overlap = len(a_idents & b_idents)
            if overlap > 0:
                return 99.0
        # Partial name match
        a_name = a.display_name.lower()
        b_name = b.display_name.lower()
        if len(a_name) > 5 and a_name in b_name or b_name in a_name:
            return 90.0
        return 0.0
