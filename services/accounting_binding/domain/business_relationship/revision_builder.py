"""
RevisionBuilder — coordinator of KnowledgeRevision construction.

Stateless. Deterministic. Creates new immutable KnowledgeRevision each call.
NO rollback/restore/merge/diff/apply/replay/compare/patch/update.
NO search/traversal. NO graph modification.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_revision_result import KnowledgeRevisionResult, KnowledgeRevisionReport
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.revision_reference import RevisionReference
from domain.business_relationship.revision_integrity import RevisionIntegrityChecker
from domain.business_relationship.revision_snapshot_factory import RevisionSnapshotFactory
from domain.business_relationship.revision_reference_factory import RevisionReferenceFactory
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.ke_explanation import GraphExplanation


class RevisionBuilder:
    """Координатор построения Revision. Не вычисляет. Не меняет."""

    def __init__(self) -> None:
        self._snapshot_factory = RevisionSnapshotFactory()
        self._reference_factory = RevisionReferenceFactory()
        self._integrity_checker = RevisionIntegrityChecker()

    def build(
        self,
        graph: KnowledgeGraph,
        *,
        provenance: KnowledgeProvenance | None = None,
        explanation: GraphExplanation | None = None,
        parent_revision_id: KnowledgeRevisionId | None = None,
        revision_number: int = 0,
        created_by: str = "",
        reason: str = "",
        document_count: int = 0,
        entity_count: int = 0,
        graph_digest_hint: str = "",
    ) -> KnowledgeRevisionResult:
        """Build a new immutable KnowledgeRevision.

        Pipeline:
          1. Create Snapshot via SnapshotFactory
          2. Create Reference via ReferenceFactory
          3. Create KnowledgeRevision
          4. Check integrity via IntegrityChecker
          5. Return Result
        """
        snapshot = self._snapshot_factory.create(
            graph=graph,
            provenance=provenance,
            explanation=explanation,
        )

        revision_id = KnowledgeRevisionId.generate()
        revision_number_obj = KnowledgeRevisionNumber(number=revision_number)
        metadata = KnowledgeRevisionMetadata(
            created_by=created_by,
            reason=reason,
            document_count=document_count,
            entity_count=entity_count,
            graph_digest_hint=graph_digest_hint,
        )

        revision = KnowledgeRevision(
            revision_id=revision_id,
            revision_number=revision_number_obj,
            snapshot=snapshot,
            metadata=metadata,
        )

        references: tuple[RevisionReference, ...] = ()
        if parent_revision_id is not None:
            ref = self._reference_factory.parent(
                parent_id=parent_revision_id,
                derived_id=revision_id,
            )
            references = (ref,)

        integrity_report = self._integrity_checker.check(
            revision=revision,
            references=references,
        )

        warnings: list[str] = []
        if integrity_report.warnings:
            warnings.extend(integrity_report.warnings)

        report = KnowledgeRevisionReport(
            revision_number=revision_number,
            nodes_total=snapshot.total_nodes,
            edges_total=snapshot.total_edges,
            warnings=tuple(warnings),
        )

        return KnowledgeRevisionResult(
            revision=revision,
            report=report,
            warnings=tuple(warnings),
        )
