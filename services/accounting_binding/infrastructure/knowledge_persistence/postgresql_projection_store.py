"""
v2.3 — PostgreSQL implementation of ProjectionStore.

Implements the ProjectionStore Protocol using psycopg2 + JSONB columns.
Stores projections and optional digests per row.

Table: projection_store

  projection_id    TEXT PRIMARY KEY
  projection_type  TEXT NOT NULL
  data             JSONB NOT NULL    ← encoded Projection fields
  digest           JSONB             ← optional ProjectionDigest
  created_at       TIMESTAMP
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from projection.projection import Projection, ProjectionId, ProjectionType
from projection.projection_digest import ProjectionDigest
from projection.exceptions import ProjectionNotFoundError

from infrastructure.knowledge_persistence.postgresql_projection_codec import (
    encode_projection,
    decode_projection,
    encode_digest,
    decode_digest,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projection_store (
    projection_id    TEXT PRIMARY KEY,
    projection_type  TEXT NOT NULL,
    data             JSONB NOT NULL DEFAULT '{}',
    digest           JSONB,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ps_projection_type
    ON projection_store(projection_type);

CREATE INDEX IF NOT EXISTS idx_ps_created_at
    ON projection_store(created_at);
"""


class PostgreSQLProjectionStore:
    """PostgreSQL implementation of ProjectionStore.

    Semantics (same as MemoryProjectionStore):
    - put() overwrites existing projection with same id (UPSERT)
    - get() raises ProjectionNotFoundError if missing
    - remove() returns True if existed
    - contains() checks existence
    - get_digest() returns stored digest or None
    - put_digest() stores/updates digest for a projection

    Connection management (same as PostgreSQLKnowledgeRevisionRepository):
    - Accepts either a DSN string or an existing psycopg2 connection
    - If DSN is provided, creates a new connection per operation
    - If connection is provided, reuses it
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
        if self._connection is not None:
            return self._connection
        if self._dsn:
            conn = psycopg2.connect(self._dsn)
            conn.autocommit = True
            return conn
        raise RuntimeError(
            "PostgreSQLProjectionStore: no DSN or connection provided"
        )

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
        finally:
            if self._connection is None:
                conn.close()

    # ── Store API ──────────────────────────────────────────────

    def put(self, projection: Projection) -> None:
        """Store or overwrite a projection."""
        encoded = encode_projection(projection)
        ptype_name = encoded["projection_type"]

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO projection_store
                       (projection_id, projection_type, data)
                       VALUES (%s, %s, %s::jsonb)
                       ON CONFLICT (projection_id)
                       DO UPDATE SET
                           projection_type = EXCLUDED.projection_type,
                           data = EXCLUDED.data,
                           created_at = NOW()""",
                    (
                        encoded["projection_id"],
                        ptype_name,
                        json.dumps(encoded),
                    ),
                )
        finally:
            if self._connection is None:
                conn.close()

    def get(self, projection_id: ProjectionId) -> Projection:
        """Get projection by id. Raises ProjectionNotFoundError if missing."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT data FROM projection_store WHERE projection_id = %s",
                    (projection_id.value,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ProjectionNotFoundError(
                        f"Projection not found: {projection_id.value}"
                    )
                return decode_projection(row["data"])
        finally:
            if self._connection is None:
                conn.close()

    def remove(self, projection_id: ProjectionId) -> bool:
        """Remove projection. Returns True if existed."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM projection_store WHERE projection_id = %s",
                    (projection_id.value,),
                )
                return cur.rowcount > 0
        finally:
            if self._connection is None:
                conn.close()

    def contains(self, projection_id: ProjectionId) -> bool:
        """Check if projection exists."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM projection_store WHERE projection_id = %s",
                    (projection_id.value,),
                )
                return cur.fetchone() is not None
        finally:
            if self._connection is None:
                conn.close()

    def get_digest(self, projection_id: ProjectionId) -> Optional[ProjectionDigest]:
        """Get stored digest for a projection, if exists."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT digest FROM projection_store WHERE projection_id = %s",
                    (projection_id.value,),
                )
                row = cur.fetchone()
                if row is None or row["digest"] is None:
                    return None
                return decode_digest(row["digest"])
        finally:
            if self._connection is None:
                conn.close()

    def put_digest(
        self, projection_id: ProjectionId, digest: ProjectionDigest
    ) -> None:
        """Store or update digest for a projection."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE projection_store
                       SET digest = %s::jsonb
                       WHERE projection_id = %s""",
                    (json.dumps(encode_digest(digest)), projection_id.value),
                )
        finally:
            if self._connection is None:
                conn.close()

    # ── Additional helpers (not in Protocol, useful for tests) ──

    def clear(self) -> None:
        """Remove all projections (for test cleanup)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM projection_store")
        finally:
            if self._connection is None:
                conn.close()

    def list_projection_ids(self) -> tuple[ProjectionId, ...]:
        """List all stored projection IDs."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT projection_id FROM projection_store ORDER BY projection_id")
                return tuple(ProjectionId(value=row[0]) for row in cur.fetchall())
        finally:
            if self._connection is None:
                conn.close()

    @property
    def count(self) -> int:
        """Total stored projections."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM projection_store")
                result = cur.fetchone()
                return result[0] if result else 0
        finally:
            if self._connection is None:
                conn.close()
