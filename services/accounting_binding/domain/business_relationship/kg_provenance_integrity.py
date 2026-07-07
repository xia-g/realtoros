"""
ProvenanceIntegrityChecker + ProvenanceIntegrityReport — structural validation.

Read-only. NO fixing. NO mutation.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.kg_provenance_chain import ProvenanceChain


@dataclass(frozen=True)
class ProvenanceIntegrityReport:
    """Отчёт о целостности происхождения. Immutable."""
    is_valid: bool = True
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ProvenanceIntegrityChecker:
    """Проверяет структуру KnowledgeProvenance. Read-only. No fix."""

    @staticmethod
    def check(chain: ProvenanceChain) -> ProvenanceIntegrityReport:
        errors: list[str] = []
        warnings: list[str] = []

        if chain.link_count == 0:
            warnings.append("Empty provenance chain: no links")

        seen_source_ids = set()
        for link in chain.links:
            if link.source.source_id in seen_source_ids:
                errors.append(f"Duplicate source id: {link.source.source_id}")
            seen_source_ids.add(link.source.source_id)

            if not (0.0 <= link.confidence <= 1.0):
                warnings.append(f"Confidence out of range: {link.confidence}")

        return ProvenanceIntegrityReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
