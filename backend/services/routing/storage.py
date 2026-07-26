"""Stream 3 — Routing storage for decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.services.routing.models import RoutingDecision


class RoutingRepository:
    """PostgreSQL storage for routing decisions.

    Product Layer, not Platform.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    def save_decision(self, decision: RoutingDecision) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO routing_decisions
                        (decision_id, document_id, rule_id, destination, status,
                         confidence, matched_entities, needs_approval,
                         created_at, routed_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (decision_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        destination = EXCLUDED.destination,
                        rule_id = EXCLUDED.rule_id,
                        matched_entities = EXCLUDED.matched_entities,
                        routed_at = EXCLUDED.routed_at,
                        metadata = EXCLUDED.metadata
                """, (
                    decision.decision_id, decision.document_id,
                    decision.rule_id or "", decision.destination, decision.status,
                    decision.confidence,
                    psycopg2.extras.Json(decision.matched_entities),
                    decision.needs_approval,
                    decision.created_at or datetime.now(timezone.utc),
                    decision.routed_at,
                    psycopg2.extras.Json(decision.metadata),
                ))
            conn.commit()
        finally:
            conn.close()

    def get_decision(self, decision_id: str) -> RoutingDecision | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM routing_decisions WHERE decision_id = %s", (decision_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return RoutingDecision(
            decision_id=str(row["decision_id"]),
            document_id=str(row["document_id"]),
            rule_id=str(row.get("rule_id", "")),
            destination=str(row.get("destination", "")),
            status=str(row.get("status", "PENDING")),
            confidence=float(row.get("confidence", 0.0)),
            matched_entities=row.get("matched_entities") or {},
            needs_approval=bool(row.get("needs_approval", False)),
            created_at=row.get("created_at"),
            routed_at=row.get("routed_at"),
            metadata=row.get("metadata") or {},
        )

    def get_decision_by_document(self, document_id: str) -> RoutingDecision | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM routing_decisions WHERE document_id = %s ORDER BY created_at DESC LIMIT 1",
                    (document_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return RoutingDecision(
            decision_id=str(row["decision_id"]),
            document_id=str(row["document_id"]),
            rule_id=str(row.get("rule_id", "")),
            destination=str(row.get("destination", "")),
            status=str(row.get("status", "PENDING")),
            confidence=float(row.get("confidence", 0.0)),
            matched_entities=row.get("matched_entities") or {},
            needs_approval=bool(row.get("needs_approval", False)),
            created_at=row.get("created_at"),
            routed_at=row.get("routed_at"),
            metadata=row.get("metadata") or {},
        )

    def update_status(self, decision_id: str, status: str,
                      destination: str = "", metadata: dict | None = None) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                now = datetime.now(timezone.utc)
                if status == "ROUTED":
                    cur.execute(
                        "UPDATE routing_decisions SET status = %s, routed_at = %s, destination = COALESCE(NULLIF(%s,''), destination), metadata = %s WHERE decision_id = %s",
                        (status, now, destination,
                         psycopg2.extras.Json(metadata or {}), decision_id),
                    )
                else:
                    cur.execute(
                        "UPDATE routing_decisions SET status = %s, destination = COALESCE(NULLIF(%s,''), destination), metadata = %s WHERE decision_id = %s",
                        (status, destination,
                         psycopg2.extras.Json(metadata or {}), decision_id),
                    )
            conn.commit()
        finally:
            conn.close()
