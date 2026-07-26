"""Pipeline storage — PostgreSQL persistence for pipelines and steps."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.services.processing.models import PipelineRun, PipelineStep


class PipelineRepository:
    """PostgreSQL repository for Document Processing Pipeline.

    Product Layer, not Platform.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    # ─── Pipeline ───────────────────────────────────────────────

    def save_pipeline(self, pipeline: PipelineRun) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO processing_pipelines
                        (pipeline_id, document_id, status, created_at, completed_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (pipeline_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        metadata = EXCLUDED.metadata
                """, (
                    pipeline.pipeline_id, pipeline.document_id,
                    pipeline.status, pipeline.created_at or datetime.now(timezone.utc),
                    pipeline.completed_at,
                    psycopg2.extras.Json(pipeline.metadata),
                ))
            conn.commit()
        finally:
            conn.close()

    def get_pipeline(self, pipeline_id: str) -> PipelineRun | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM processing_pipelines WHERE pipeline_id = %s", (pipeline_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return PipelineRun(
            pipeline_id=str(row["pipeline_id"]),
            document_id=str(row["document_id"]),
            status=str(row["status"]),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
            metadata=row.get("metadata") or {},
        )

    def get_pipeline_by_document(self, document_id: str) -> PipelineRun | None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM processing_pipelines WHERE document_id = %s ORDER BY created_at DESC LIMIT 1",
                    (document_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return PipelineRun(
            pipeline_id=str(row["pipeline_id"]),
            document_id=str(row["document_id"]),
            status=str(row["status"]),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
            metadata=row.get("metadata") or {},
        )

    def update_pipeline_status(self, pipeline_id: str, status: str, completed_at: datetime | None = None) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE processing_pipelines SET status = %s, completed_at = COALESCE(%s, completed_at) WHERE pipeline_id = %s",
                    (status, completed_at or datetime.now(timezone.utc), pipeline_id),
                )
            conn.commit()
        finally:
            conn.close()

    # ─── Steps ──────────────────────────────────────────────────

    def save_step(self, step: PipelineStep) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO processing_steps
                        (step_id, pipeline_id, step_type, status, order_index, started_at, completed_at, result, error)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (step_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error
                """, (
                    step.step_id, step.pipeline_id, step.step_type,
                    step.status, step.order_index,
                    step.started_at, step.completed_at,
                    psycopg2.extras.Json(step.result) if step.result else psycopg2.extras.Json({}),
                    step.error or "",
                ))
            conn.commit()
        finally:
            conn.close()

    def get_steps(self, pipeline_id: str) -> list[PipelineStep]:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM processing_steps WHERE pipeline_id = %s ORDER BY order_index",
                    (pipeline_id,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return [
            PipelineStep(
                step_id=str(r["step_id"]),
                pipeline_id=str(r["pipeline_id"]),
                step_type=str(r["step_type"]),
                status=str(r["status"]),
                order_index=int(r["order_index"]),
                started_at=r.get("started_at"),
                completed_at=r.get("completed_at"),
                result=r.get("result") or {},
                error=r.get("error") or "",
            )
            for r in rows
        ]

    def update_step_status(self, step_id: str, status: str, error: str = "", result: dict | None = None) -> None:
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                now = datetime.now(timezone.utc)
                if status in ("COMPLETED", "FAILED"):
                    cur.execute(
                        "UPDATE processing_steps SET status = %s, completed_at = %s, error = %s, result = %s WHERE step_id = %s",
                        (status, now, error or "",
                         psycopg2.extras.Json(result or {}), step_id),
                    )
                elif status == "RUNNING":
                    cur.execute(
                        "UPDATE processing_steps SET status = %s, started_at = %s WHERE step_id = %s",
                        (status, now, step_id),
                    )
                else:
                    cur.execute(
                        "UPDATE processing_steps SET status = %s WHERE step_id = %s",
                        (status, step_id),
                    )
            conn.commit()
        finally:
            conn.close()
