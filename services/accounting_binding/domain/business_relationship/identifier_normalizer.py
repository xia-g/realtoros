"""
IdentifierNormalizer — normalizes entity identifiers.

Stateless. Deterministic. No matching or merging.
Wraps existing NormalizationService with typed output.
"""
from __future__ import annotations

from domain.business_relationship.entity_types import IdentifierType
from domain.business_relationship.normalization import NormalizationService
from domain.business_relationship.entity_identifier import EntityIdentifier as RawEntityIdentifier
from domain.business_relationship.normalized_identifier import NormalizedIdentifier


class IdentifierNormalizer:
    """Нормализует идентификаторы. Без поиска совпадений или слияния."""

    @staticmethod
    def normalize(
        identifier_type: IdentifierType,
        value: str,
        confidence: float = 1.0,
    ) -> NormalizedIdentifier:
        """Нормализовать один идентификатор."""
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
        normalizer = normalizers.get(identifier_type, lambda x: x.strip())
        normalized = normalizer(value)
        return NormalizedIdentifier(
            identifier_type=identifier_type,
            original=value,
            normalized=normalized,
            confidence=confidence,
        )

    @staticmethod
    def normalize_many(
        identifiers: list[RawEntityIdentifier],
    ) -> list[NormalizedIdentifier]:
        """Нормализовать список идентификаторов."""
        return [
            IdentifierNormalizer.normalize(
                identifier_type=idf.identifier_type,
                value=idf.value,
                confidence=idf.confidence,
            )
            for idf in identifiers
        ]
