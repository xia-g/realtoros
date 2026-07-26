"""
Knowledge Audit Trail v1 — models and stateless service.

Pure functions over existing KnowledgeRevision + KnowledgeSnapshot.
No Platform changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata
from domain.business_relationship.kg_enums import GraphNodeType, GraphEdgeType
from domain.business_relationship.kg_provenance_source import ProvenanceSourceType

from application.capabilities.consistency_check import check_snapshot_consistency


# ─── Models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuditProvenanceEntry:
    source_type: str
    source_id: str
    description: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class AuditRevisionSummary:
    revision_id: str
    revision_number: int
    created_at: str
    created_by: str = ""
    reason: str = ""
    source_document_id: str = ""


@dataclass(frozen=True)
class AuditValidationSummary:
    is_consistent: bool
    violations_count: int
    errors: int = 0
    warnings: int = 0


@dataclass(frozen=True)
class AuditTrailResult:
    """Full audit trail for a KnowledgeRevision."""
    revision: AuditRevisionSummary
    provenance: tuple[AuditProvenanceEntry, ...] = ()
    validation: AuditValidationSummary | None = None
    previous_revision: AuditRevisionSummary | None = None
    next_revision: AuditRevisionSummary | None = None
    total_revisions_for_document: int = 0


# ─── Service ─────────────────────────────────────────────────────


class KnowledgeAuditService:
    """Stateless audit trail service.

    Reads from existing KnowledgeRevision + KnowledgeSnapshot.
    Consistency Check is computed on demand.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _execute_query(self, sql: str, params: tuple) -> list[dict[str, Any]]:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(self._dsn)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _revision_summary(self, row: dict) -> AuditRevisionSummary:
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                import json
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
        return AuditRevisionSummary(
            revision_id=str(row["revision_id"]),
            revision_number=int(row["revision_number"]),
            created_at=str(row["created_at"]) if row.get("created_at") else "",
            created_by=str(meta.get("created_by", "")) if isinstance(meta, dict) else "",
            reason=str(meta.get("reason", "")) if isinstance(meta, dict) else "",
            source_document_id=str(row.get("source_document_id", "")),
        )

    def build_audit(
        self,
        revision: KnowledgeRevision,
        source_document_id: str,
    ) -> AuditTrailResult:
        """Build the full audit trail for a given revision.

        Args:
            revision: The KnowledgeRevision to audit.
            source_document_id: The source document ID from the record.

        Returns:
            AuditTrailResult with revision summary, provenance,
            validation, and navigation.
        """
        # Revision summary
        meta = revision.metadata
        rev_summary = AuditRevisionSummary(
            revision_id=revision.revision_id.value,
            revision_number=revision.revision_number.number,
            created_at=str(meta.created_at) if meta.created_at else "",
            created_by=meta.created_by or "",
            reason=meta.reason or "",
            source_document_id=source_document_id,
        )

        # Provenance from snapshot
        provenance: list[AuditProvenanceEntry] = []
        snapshot = revision.snapshot
        if snapshot and snapshot.provenance:
            for link in snapshot.provenance.chain.links:
                st = link.source.source_type.value if hasattr(link.source.source_type, "value") else str(link.source.source_type)
                provenance.append(AuditProvenanceEntry(
                    source_type=st,
                    source_id=link.source.source_id,
                    description=link.source.description,
                    confidence=link.confidence,
                ))

        # Consistency check (on demand)
        validation = None
        if snapshot:
            c_result = check_snapshot_consistency(snapshot)
            validation = AuditValidationSummary(
                is_consistent=c_result.is_consistent,
                violations_count=len(c_result.violations),
                errors=c_result.errors,
                warnings=c_result.warnings,
            )

        # Previous / next revision (from DB)
        prev_rev = None
        next_rev = None
        total_count = 0

        if source_document_id:
            rows = self._execute_query(
                """SELECT revision_id, revision_number, source_document_id, created_at, metadata
                   FROM knowledge_revisions
                   WHERE source_document_id = %s
                   ORDER BY created_at ASC, revision_id ASC""",
                (source_document_id,),
            )
            total_count = len(rows)
            current_idx = None
            for i, row in enumerate(rows):
                if row["revision_id"] == revision.revision_id.value:
                    current_idx = i
                    break

            if current_idx is not None:
                if current_idx > 0:
                    prev_rev = self._revision_summary(rows[current_idx - 1])
                if current_idx < len(rows) - 1:
                    next_rev = self._revision_summary(rows[current_idx + 1])

        return AuditTrailResult(
            revision=rev_summary,
            provenance=tuple(provenance),
            validation=validation,
            previous_revision=prev_rev,
            next_revision=next_rev,
            total_revisions_for_document=total_count,
        )
