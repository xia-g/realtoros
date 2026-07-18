"""
RevisionIntegrityChecker + RevisionIntegrityReport — structural validation.

Read-only. NO fixing. NO mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.revision_reference import RevisionReference


@dataclass(frozen=True)
class RevisionIntegrityReport:
    """Агрегированная информация о целостности. Immutable. Без логики."""
    duplicate_revision_numbers: int = 0
    missing_snapshot: bool = False
    missing_metadata: bool = False
    missing_reference: bool = False
    empty_snapshot: bool = False
    warnings: tuple[str, ...] = ()


class RevisionIntegrityChecker:
    """Проверяет структуру Revision. Read-only. Никогда не исправляет."""

    @staticmethod
    def check(
        revision: KnowledgeRevision,
        references: tuple[RevisionReference, ...] = (),
    ) -> RevisionIntegrityReport:
        """Возвращает Report. Никаких исключений."""
        warnings: list[str] = []
        dup_numbers = 0
        missing_snap = revision.snapshot is None
        missing_meta = revision.metadata is None
        missing_ref = len(references) == 0

        if revision.snapshot is not None:
            if revision.snapshot.total_nodes == 0 and revision.snapshot.total_edges == 0:
                empty_snapshot = True
                warnings.append("snapshot is empty (no nodes or edges)")
            else:
                empty_snapshot = False
        else:
            empty_snapshot = False

        if missing_snap:
            warnings.append("snapshot is missing")
        if missing_meta:
            warnings.append("metadata is missing")
        if missing_ref:
            warnings.append("no references provided")

        return RevisionIntegrityReport(
            duplicate_revision_numbers=dup_numbers,
            missing_snapshot=missing_snap,
            missing_metadata=missing_meta,
            missing_reference=missing_ref,
            empty_snapshot=empty_snapshot,
            warnings=tuple(warnings),
        )
