"""
v2.3 — PostgreSQL implementation of KnowledgeRevisionRepository.

Implements the KnowledgeRevisionRepository Protocol using psycopg2.
Stores revision data as JSONB columns for flexibility.

Table: knowledge_revisions

  revision_id          TEXT PRIMARY KEY (UUID)
  revision_number      INTEGER NOT NULL
  source_document_id   TEXT NOT NULL
  processing_job_id    TEXT
  created_at           TIMESTAMP
  snapshot_graph       JSONB
  snapshot_provenance  JSONB
  snapshot_explanation JSONB
  explanation          JSONB
  metadata             JSONB
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.kg_graph import KnowledgeGraph
from domain.business_relationship.kg_provenance import KnowledgeProvenance
from domain.business_relationship.ke_explanation import GraphExplanation

from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionConflictError,
)

from infrastructure.knowledge_persistence.postgresql_codec import (
    serialise_snapshot,
    deserialise_snapshot,
    serialise_metadata,
    deserialise_metadata,
    _ser_explanation,
    _deser_explanation,
    _dt_to_str,
    _str_to_dt,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_revisions (
    revision_id          TEXT PRIMARY KEY,
    revision_number      INTEGER NOT NULL,
    source_document_id   TEXT NOT NULL,
    processing_job_id    TEXT,
    created_at           TIMESTAMP,
    snapshot_graph       JSONB NOT NULL DEFAULT '{}',
    snapshot_provenance  JSONB,
    snapshot_explanation JSONB,
    explanation          JSONB,
    metadata             JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_kr_source_doc
    ON knowledge_revisions(source_document_id);

CREATE INDEX IF NOT EXISTS idx_kr_created_at
    ON knowledge_revisions(created_at);
"""


class PostgreSQLKnowledgeRevisionRepository:
    """PostgreSQL implementation of KnowledgeRevisionRepository.

    Semantics (same as MemoryKnowledgeRevisionRepository):
    - save() with same revision_id and identical record → idempotent success (UPSERT)
    - save() with same revision_id but different content → KnowledgeRevisionConflictError
    - get() returns None for missing revision
    - get_by_document_id() returns all revisions for a document (sorted by created_at)

    Connection management:
    - Accepts either a DSN string or an existing psycopg2 connection
    - If DSN is provided, creates a new connection per operation
    - If connection is provided, uses it directly
    """

    def __init__(
        self,
        dsn: str = "",
        connection=None,
        auto_create_table: bool = True,
    ) -> None:
        self._dsn = dsn
        self._connection = connection
        if auto_create_table:
            self._ensure_table()

    # ── Connection helpers ─────────────────────────────────────

    def _get_conn(self):
        """Get a psycopg2 connection."""
        if self._connection is not None:
            return self._connection
        if self._dsn:
            conn = psycopg2.connect(self._dsn)
            conn.autocommit = True
            return conn
        raise RuntimeError(
            "PostgreSQLKnowledgeRevisionRepository: no DSN or connection provided"
        )

    def _ensure_table(self) -> None:
        """Create the table if it doesn't exist."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
        finally:
            if self._connection is None:
                conn.close()

    # ── Serialisation ─────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: dict) -> KnowledgeRevisionRecord:
        """Convert a database row dict to KnowledgeRevisionRecord."""
        snapshot = deserialise_snapshot({
            "graph": row.get("snapshot_graph") or {},
            "provenance": row.get("snapshot_provenance"),
            "explanation": row.get("snapshot_explanation"),
        })
        explanation_data = row.get("explanation")
        explanation = _deser_explanation(explanation_data) if explanation_data else snapshot.explanation
        meta = deserialise_metadata(row.get("metadata"))
        created_at = row.get("created_at")
        if isinstance(created_at, datetime):
            dt = created_at
        else:
            dt = _str_to_dt(created_at)
        revision = KnowledgeRevision(
            revision_id=KnowledgeRevisionId(value=row["revision_id"]),
            revision_number=KnowledgeRevisionNumber(number=row["revision_number"]),
            snapshot=snapshot,
            metadata=meta,
        )
        return KnowledgeRevisionRecord(
            revision=revision,
            explanation=explanation,
            source_document_id=row["source_document_id"],
            processing_job_id=row.get("processing_job_id"),
            created_at=dt,
        )

    @staticmethod
    def _record_to_row(record: KnowledgeRevisionRecord) -> dict:
        """Convert KnowledgeRevisionRecord to database row dict."""
        rev = record.revision
        snap = serialise_snapshot(rev.snapshot)
        return {
            "revision_id": rev.revision_id.value,
            "revision_number": rev.revision_number.number,
            "source_document_id": record.source_document_id,
            "processing_job_id": record.processing_job_id,
            "created_at": record.created_at if record.created_at != datetime.min else rev.metadata.created_at,
            "snapshot_graph": json.dumps(snap["graph"] if snap else {}),
            "snapshot_provenance": json.dumps(snap["provenance"]) if snap and snap.get("provenance") else None,
            "snapshot_explanation": json.dumps(snap["explanation"]) if snap and snap.get("explanation") else None,
            "explanation": json.dumps(_ser_explanation(record.explanation)),
            "metadata": json.dumps(serialise_metadata(rev.metadata)),
        }

    # ── Repository API ────────────────────────────────────────

    def save(self, record: KnowledgeRevisionRecord) -> None:
        """Persist a revision record via UPSERT with conflict detection.

        If same revision_id exists:
          - identical content → idempotent (no-op)
          - different content → KnowledgeRevisionConflictError
        """
        rev_id = record.revision.revision_id.value
        row = self._record_to_row(record)

        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # First check if revision exists
                cur.execute(
                    "SELECT revision_id, snapshot_graph, source_document_id "
                    "FROM knowledge_revisions WHERE revision_id = %s",
                    (rev_id,),
                )
                existing = cur.fetchone()

                if existing:
                    # Conflict detection: compare canonical content
                    # (graph nodes/edges structure, source doc — skip timestamps)
                    existing_graph = existing["snapshot_graph"]
                    existing_nodes = sorted(existing_graph.get("nodes", []), key=lambda n: n.get("node_id", ""))
                    existing_edges = sorted(existing_graph.get("edges", []), key=lambda e: e.get("edge_id", ""))
                    new_graph = json.loads(row["snapshot_graph"])
                    new_nodes = sorted(new_graph.get("nodes", []), key=lambda n: n.get("node_id", ""))
                    new_edges = sorted(new_graph.get("edges", []), key=lambda e: e.get("edge_id", ""))

                    def _strip_meta(items: list[dict]) -> list[dict]:
                        """Remove metadata timestamps for comparison."""
                        result = []
                        for item in items:
                            cleaned = {k: v for k, v in item.items() if k != "metadata"}
                            if "metadata" in item and isinstance(item["metadata"], dict):
                                cleaned["metadata"] = {
                                    k: v for k, v in item["metadata"].items()
                                    if k != "created_at"
                                }
                            result.append(cleaned)
                        return result

                    if (_strip_meta(existing_nodes) != _strip_meta(new_nodes)
                            or _strip_meta(existing_edges) != _strip_meta(new_edges)
                            or existing["source_document_id"] != row["source_document_id"]):
                        raise KnowledgeRevisionConflictError(
                            f"Revision {rev_id} already exists with different content"
                        )
                    # Idempotent: same content → no-op
                    return

                # UPSERT: insert new
                cur.execute(
                    """INSERT INTO knowledge_revisions
                       (revision_id, revision_number, source_document_id,
                        processing_job_id, created_at,
                        snapshot_graph, snapshot_provenance, snapshot_explanation,
                        explanation, metadata)
                       VALUES (%(revision_id)s, %(revision_number)s, %(source_document_id)s,
                               %(processing_job_id)s, %(created_at)s,
                               %(snapshot_graph)s::jsonb, %(snapshot_provenance)s::jsonb,
                               %(snapshot_explanation)s::jsonb,
                               %(explanation)s::jsonb, %(metadata)s::jsonb)
                       ON CONFLICT (revision_id) DO NOTHING""",
                    row,
                )
        finally:
            if self._connection is None:
                conn.close()

    def get(self, revision_id: KnowledgeRevisionId) -> KnowledgeRevisionRecord | None:
        """Retrieve a revision record by its ID."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM knowledge_revisions WHERE revision_id = %s",
                    (revision_id.value,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._row_to_record(row)
        finally:
            if self._connection is None:
                conn.close()

    def get_by_document_id(
        self,
        source_document_id: str,
    ) -> tuple[KnowledgeRevisionRecord, ...]:
        """Retrieve all revision records for a given source document,
        ordered by revision_number ascending."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM knowledge_revisions WHERE source_document_id = %s "
                    "ORDER BY revision_number ASC",
                    (source_document_id,),
                )
                rows = cur.fetchall()
                return tuple(self._row_to_record(r) for r in rows)
        finally:
            if self._connection is None:
                conn.close()

    def exists(self, revision_id: KnowledgeRevisionId | str) -> bool:
        """Check if a revision exists by ID.
        
        Accepts both str and KnowledgeRevisionId for convenience.
        """
        rid = revision_id.value if isinstance(revision_id, KnowledgeRevisionId) else revision_id
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM knowledge_revisions WHERE revision_id = %s",
                    (rid,),
                )
                return cur.fetchone() is not None
        finally:
            if self._connection is None:
                conn.close()

    def __len__(self) -> int:
        """Return total count of stored revisions."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM knowledge_revisions")
                return cur.fetchone()[0]
        finally:
            if self._connection is None:
                conn.close()

    def delete_all(self) -> None:
        """Remove all rows (for test cleanup)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_revisions")
        finally:
            if self._connection is None:
                conn.close()
