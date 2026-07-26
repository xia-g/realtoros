"""
Knowledge Search v1 — search service.

Stateless. Pure SQL over existing knowledge_revisions table.
No Platform changes. No Domain imports beyond query/result models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from application.capabilities.search_models import (
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
    SearchResultItem,
    encode_search_cursor,
    decode_search_cursor,
)


class KnowledgeSearchService:
    """Search service for KnowledgeRevision.

    Executes deterministic SQL queries against the existing
    knowledge_revisions table. No changes to Platform.

    Identity contract and ordering:
      ORDER BY created_at DESC, revision_id DESC
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

    def search(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult:
        """Execute a search query and return deterministic results."""
        conditions: list[str] = []
        params: list[Any] = []

        if query.source_document_id:
            conditions.append("source_document_id = %s")
            params.append(query.source_document_id)

        if query.reason_contains:
            conditions.append("metadata->>'reason' ILIKE %s")
            params.append(f"%{query.reason_contains}%")

        if query.created_by:
            conditions.append("metadata->>'created_by' = %s")
            params.append(query.created_by)

        if query.created_after:
            conditions.append("created_at >= %s::timestamp")
            params.append(query.created_after)

        if query.created_before:
            conditions.append("created_at <= %s::timestamp")
            params.append(query.created_before)

        if query.revision_number_min is not None:
            conditions.append("revision_number >= %s")
            params.append(query.revision_number_min)

        if query.revision_number_max is not None:
            conditions.append("revision_number <= %s")
            params.append(query.revision_number_max)

        where = " AND ".join(conditions) if conditions else "TRUE"

        # Validate sort field
        sort_col = "created_at" if query.sort_field == "created_at" else "revision_number"
        sort_dir = "DESC" if query.sort_direction == "DESC" else "ASC"
        # Tiebreaker for determinism
        tiebreaker = "DESC" if sort_dir == "DESC" else "ASC"

        # Cursor
        if query.cursor:
            try:
                cursor_ca, cursor_rid = decode_search_cursor(query.cursor)
            except (ValueError, Exception):
                # Invalid cursor → return empty
                return KnowledgeSearchResult()

            # Compare operators depend on sort direction
            if sort_dir == "DESC":
                cmp_op = "<"
            else:
                cmp_op = ">"

            cursor_condition = (
                f"({sort_col}, revision_id) {cmp_op} (%s::timestamp, %s)"
                if sort_col == "created_at"
                else f"({sort_col}, created_at) {cmp_op} (%s, %s)"
            )
            if sort_col == "created_at":
                cursor_params = [cursor_ca, cursor_rid]
            else:
                cursor_params = [int(cursor_ca), cursor_rid]

            sql = f"""
                SELECT revision_id, revision_number, source_document_id,
                       created_at, metadata
                FROM knowledge_revisions
                WHERE {where} AND {cursor_condition}
                ORDER BY {sort_col} {sort_dir}, revision_id {tiebreaker}
                LIMIT %s
            """
            params = list(params) + cursor_params + [query.limit + 1]
        else:
            sql = f"""
                SELECT revision_id, revision_number, source_document_id,
                       created_at, metadata
                FROM knowledge_revisions
                WHERE {where}
                ORDER BY {sort_col} {sort_dir}, revision_id {tiebreaker}
                LIMIT %s
            """
            params = list(params) + [query.limit + 1]

        rows = self._execute_query(sql, tuple(params))

        has_more = len(rows) > query.limit
        items = rows[:query.limit]

        result_items: list[SearchResultItem] = []
        next_cursor = None

        for i, row in enumerate(items):
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    import json
                    meta = json.loads(meta)
                except (ValueError, TypeError):
                    meta = {}

            result_items.append(SearchResultItem(
                revision_id=str(row["revision_id"]),
                revision_number=int(row["revision_number"]),
                source_document_id=str(row["source_document_id"]),
                created_at=str(row["created_at"]) if row.get("created_at") else "",
                reason=str(meta.get("reason", "")) if isinstance(meta, dict) else "",
                created_by=str(meta.get("created_by", "")) if isinstance(meta, dict) else "",
            ))

            # Cursor = last item of the current page
            if has_more and i == len(items) - 1:
                ca = str(row["created_at"]) if row.get("created_at") else str(result_items[-1].created_at)
                rid = str(row["revision_id"])
                next_cursor = encode_search_cursor(ca, rid)

        return KnowledgeSearchResult(
            items=tuple(result_items),
            next_cursor=next_cursor,
            total_matches=len(result_items),
        )
