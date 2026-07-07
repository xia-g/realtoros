"""
IdentityResolver — coordinator of identity resolution.

Pipeline:
  EntityIdentifier → IdentifierNormalizer
                  → IdentityCandidate
                  → IdentityMatcher
                  → CanonicalEntity (ONE constructor call)

Deterministic. Stateless. Side-effect free.
NO post-construction mutation of CanonicalEntity.
"""
from __future__ import annotations

from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.business_relationship.entity import BusinessEntity
from domain.business_relationship.entity_identifier import EntityIdentifier
from domain.business_relationship.entity_alias import EntityAlias, AliasType
from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.normalized_identifier import NormalizedIdentifier
from domain.business_relationship.identity_candidate import IdentityCandidate
from domain.business_relationship.identity_evidence import IdentityEvidence
from domain.business_relationship.identity_match_result import IdentityMatchResult, MatchDecision
from domain.business_relationship.identity_resolution_result import (
    IdentityResolutionResult, IdentityResolutionReport,
)
from domain.business_relationship.canonical_entity import CanonicalEntity
from domain.business_relationship.canonical_entity_id import CanonicalEntityId


class IdentityResolver:
    """Разрешает идентичность: факты → кандидат → CanonicalEntity.

    Stateless. Deterministic. Immutable output.
    """

    @staticmethod
    def resolve(
        entity: BusinessEntity,
        identifiers: list[EntityIdentifier],
        document_id: str,
        existing_entities: list[CanonicalEntity] | None = None,
    ) -> IdentityResolutionResult:
        """Разрешить одну бизнес-сущность в CanonicalEntity.

        1. Normalize all identifiers
        2. Build IdentityCandidate
        3. Match against existing entities
        4. Create CanonicalEntity (ONE call, fully formed)
        """
        existing = existing_entities or []

        # 1. Normalize
        normalized = IdentityResolver._normalize_identifiers(identifiers)

        # 2. Build candidate
        candidate = IdentityResolver._build_candidate(entity, normalized)

        # 3. Match
        match = IdentityResolver._match(candidate, existing)

        # 4. Create CanonicalEntity (match or new)
        if match.decision == MatchDecision.MATCH and match.matched_entity:
            return IdentityResolutionResult(
                entity=match.matched_entity,
                candidate=candidate,
                match_result=match,
            )

        # Build aliases from normalized identifiers that differ from original
        aliases: list[EntityAlias] = []
        for ni in normalized:
            if ni.original != ni.normalized:
                aliases.append(EntityAlias(
                    original_value=ni.original,
                    normalized_value=ni.normalized,
                    alias_type=AliasType.NAME_VARIANT,
                    source_document_id=document_id,
                ))

        # Build evidence
        evidence = tuple(
            IdentityEvidence(source_document_id=document_id, confidence=idf.confidence)
            for idf in identifiers
        )

        # Build identifiers tuple for CanonicalEntity
        entity_idfs = tuple(
            __import__('domain.business_relationship.entity_identifier', fromlist=['EntityIdentifier']).EntityIdentifier(
                identifier_type=ni.identifier_type,
                value=ni.normalized,
                confidence=ni.confidence,
                source_document_id=document_id,
            )
            for ni in normalized
        )

        # ONE constructor call — fully formed
        ce = CanonicalEntity(
            entity_type=candidate.entity_type,
            id=CanonicalEntityId.generate(),
            display_name=candidate.display_name,
            identifiers=entity_idfs,
            aliases=tuple(aliases),
            evidence=evidence,
        )

        return IdentityResolutionResult(
            entity=ce,
            candidate=candidate,
            match_result=match,
        )

    @staticmethod
    def _normalize_identifiers(
        identifiers: list[EntityIdentifier],
    ) -> list[NormalizedIdentifier]:
        """Normalize all identifiers."""
        ns = NormalizationService
        normalizers = {
            IdentifierType.INN: ns.normalize_inn,
            IdentifierType.OGRN: ns.normalize_ogrn,
            IdentifierType.PHONE: ns.normalize_phone,
            IdentifierType.EMAIL: ns.normalize_email,
            IdentifierType.ADDRESS: ns.normalize_address,
            IdentifierType.CONTRACT_NUMBER: ns.normalize_contract_number,
            IdentifierType.CADASTRE: ns.normalize_cadastre,
            IdentifierType.BANK_ACCOUNT: ns.normalize_bank_account,
        }
        result: list[NormalizedIdentifier] = []
        for idf in identifiers:
            normalizer = normalizers.get(idf.identifier_type, lambda x: x.strip())
            normalized = normalizer(idf.value)
            result.append(NormalizedIdentifier(
                identifier_type=idf.identifier_type,
                original=idf.value,
                normalized=normalized,
                confidence=idf.confidence,
            ))
        return result

    @staticmethod
    def _build_candidate(
        entity: BusinessEntity,
        normalized: list[NormalizedIdentifier],
    ) -> IdentityCandidate:
        """Build IdentityCandidate from entity and normalized identifiers."""
        display = entity.display_name
        for ni in normalized:
            if ni.identifier_type == IdentifierType.INN and ni.normalized:
                display = ni.normalized
        return IdentityCandidate(
            entity_type=entity.entity_type,
            display_name=display,
            identifiers=tuple(normalized),
        )

    @staticmethod
    def _match(
        candidate: IdentityCandidate,
        existing: list[CanonicalEntity],
    ) -> IdentityMatchResult:
        """Match candidate against existing CanonicalEntities."""
        if not candidate.identifiers:
            return IdentityMatchResult(
                decision=MatchDecision.NO_MATCH,
                candidate=candidate,
                reason="No identifiers to match",
            )

        candidate_ids = set(ni.normalized for ni in candidate.identifiers if ni.normalized)
        matched: list[CanonicalEntity] = []
        for ce in existing:
            ce_ids = set(idf.value for idf in ce.identifiers)
            if candidate_ids & ce_ids:
                matched.append(ce)

        if len(matched) == 1:
            return IdentityMatchResult(
                decision=MatchDecision.MATCH,
                candidate=candidate,
                matched_entity=matched[0],
                reason="Identifier match with existing entity",
            )
        if len(matched) > 1:
            return IdentityMatchResult(
                decision=MatchDecision.AMBIGUOUS,
                candidate=candidate,
                reason=f"Multiple ({len(matched)}) entities match identifiers",
            )
        return IdentityMatchResult(
            decision=MatchDecision.NO_MATCH,
            candidate=candidate,
            reason="No existing entity matches",
        )
