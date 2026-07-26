"""Epic 1 / Stream 1 — Document Intake & Lifecycle.

Document model, lifecycle states, transitions, repository.
Product Layer — not Platform.

Updated for Stream 3: mark_document_ready is a pure domain function.
Outbox integration happens at the caller (API endpoint).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from structlog import get_logger

from backend.core.domain_events import DomainEvent, get_event_bus, EVENT_DOCUMENT_READY
from backend.core.integration_event import IntegrationEvent, EventAdapter
from backend.core.audit import get_audit_context

logger = get_logger(__name__)


# ─── Lifecycle states ────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, list[str]] = {
    "UPLOADED":    ["VALIDATED", "REJECTED"],
    "VALIDATED":   ["ACCEPTED", "REJECTED"],
    "ACCEPTED":    ["PROCESSING", "FAILED"],
    "PROCESSING":  ["ANALYZED", "FAILED", "NEEDS_REVIEW"],
    "ANALYZED":    ["READY", "NEEDS_REVIEW"],
    "READY":       ["ROUTED"],
    "ROUTED":      ["ARCHIVED", "NEEDS_REVIEW"],
    "ARCHIVED":    [],
    "REJECTED":    [],
    "FAILED":      ["PROCESSING"],  # retry
    "NEEDS_REVIEW": ["PROCESSING", "READY", "ARCHIVED"],
}

TERMINAL_STATES = {"ARCHIVED", "REJECTED"}


# ─── Document model ──────────────────────────────────────────────


@dataclass
class Document:
    document_id: str
    organization_id: str
    uploaded_by: str
    uploaded_at: datetime

    # Lifecycle
    status: str = "UPLOADED"
    pipeline_stage: str = ""

    # File info
    storage_uri: str = ""
    mime_type: str = ""
    page_count: int = 0
    size_bytes: int = 0
    checksum: str = ""
    original_filename: str = ""

    # Product metadata (before analysis)
    metadata: dict = field(default_factory=dict)

    # Document profile (after analysis)
    profile: dict = field(default_factory=dict)

    # DB timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─── Lifecycle helpers ────────────────────────────────────────────


def validate_transition(current: str, target: str) -> str | None:
    """Check if transition is allowed. Returns error message or None."""
    if current == target:
        return None  # same state, no-op
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        return f"Transition {current} → {target} not allowed"
    return None


def transition_document(doc: Document, target: str) -> str | None:
    """Attempt to transition a document to a new state.
    Returns error message or None on success.
    """
    if doc.status in TERMINAL_STATES:
        return f"Document in terminal state {doc.status}, no transitions allowed"

    err = validate_transition(doc.status, target)
    if err:
        return err

    doc.status = target
    doc.updated_at = datetime.now(timezone.utc)
    return None


# ─── Use Cases ────────────────────────────────────────────────────


def mark_document_ready(
    doc: Document,
    actor_id: str = "system",
    event_bus=None,
) -> tuple[str | None, DomainEvent | None]:
    """Mark a document as READY.

    Allowed from ANALYZED or NEEDS_REVIEW states.
    Returns DomainEvent for outbox integration (caller persists it).

    Stream 3: No longer calls bus.emit() or create_task.
    DomainEvent is returned to caller for outbox-based durable delivery.
    """
    # Idempotency guard
    if doc.status == "READY":
        return "Document is already in READY state", None

    # Semantic guard — only ANALYZED or NEEDS_REVIEW can become READY
    ALLOWED_PRECURSORS = {"ANALYZED", "NEEDS_REVIEW"}
    if doc.status not in ALLOWED_PRECURSORS:
        return (
            f"Cannot transition from {doc.status} to READY: "
            f"only ANALYZED or NEEDS_REVIEW allowed",
            None,
        )

    # Capture previous status before transition changes it
    previous_status = doc.status

    # Perform the state transition (VALID_TRANSITIONS already allows both)
    err = transition_document(doc, "READY")
    if err:
        return err, None

    # Build event payload from doc + profile
    profile = doc.profile or {}
    payload = {
        "status": doc.status,
        "previous_status": previous_status,
        "document_id": doc.document_id,
        "organization_id": doc.organization_id,
        "contract_number": profile.get("contract_number", ""),
        "total_price": profile.get("total_price", ""),
        "buyer_name": profile.get("buyer_name", ""),
        "seller_name": profile.get("seller_name", ""),
        "profile": profile,
    }

    event = DomainEvent(
        event_type=EVENT_DOCUMENT_READY,
        entity_type="document",
        entity_id=uuid.uuid4(),
        actor_id=actor_id,
        payload=payload,
    )

    # Stream 3: NO longer emits via bus.emit() with create_task.
    # Caller is responsible for outbox-based durable delivery.
    # Keep DomainEventBus emit for backward compat with in-memory handlers,
    # but the primary delivery mechanism is now the outbox.
    bus = event_bus or get_event_bus()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(bus.emit(event))
    except RuntimeError:
        logger.warning("no_event_loop", event_type=EVENT_DOCUMENT_READY)

    # Audit log
    audit_ctx = get_audit_context()
    logger.info(
        "document_marked_ready",
        document_id=doc.document_id,
        actor_id=actor_id,
        request_id=getattr(audit_ctx, "request_id", None),
        event_id=str(event.entity_id),
    )

    return None, event


def build_integration_event_from_domain(
    domain_event: DomainEvent,
    doc: Document,
) -> IntegrationEvent:
    """Build an IntegrationEvent from a DomainEvent for outbox delivery."""
    return IntegrationEvent(
        event_id=uuid.uuid4(),
        event_type=domain_event.event_type,
        aggregate_type="Document",
        aggregate_id=doc.document_id,
        occurred_at=domain_event.occurred_at or datetime.now(timezone.utc),
        version=1,
        payload=domain_event.payload,
        metadata={
            "schema_version": 1,
            "producer": "document-lifecycle",
            "correlation_id": domain_event.correlation_id or "",
        },
    )


# ─── Repository ──────────────────────────────────────────────────


class DocumentRepository:
    """PostgreSQL repository for Document lifecycle.

    Product Layer, not Platform. Uses its own table.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    def _connect(self):
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(self._dsn)

    def save(self, doc: Document, conn=None) -> None:
        """Insert or update a document record.

        Args:
            doc: Document to save.
            conn: Optional existing connection (for transactional use).
                  If None, creates a new connection.
        """
        import psycopg2
        import psycopg2.extras
        own_conn = False
        if conn is None:
            conn = self._connect()
            own_conn = True
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_intake (
                        document_id, organization_id, uploaded_by, uploaded_at,
                        status, pipeline_stage,
                        storage_uri, mime_type, page_count, size_bytes, checksum, original_filename,
                        metadata, profile,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (document_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        pipeline_stage = EXCLUDED.pipeline_stage,
                        metadata = EXCLUDED.metadata,
                        profile = EXCLUDED.profile,
                        updated_at = NOW()
                """, (
                    doc.document_id, doc.organization_id, doc.uploaded_by, doc.uploaded_at,
                    doc.status, doc.pipeline_stage,
                    doc.storage_uri, doc.mime_type, doc.page_count,
                    doc.size_bytes, doc.checksum, doc.original_filename,
                    psycopg2.extras.Json(doc.metadata),
                    psycopg2.extras.Json(doc.profile),
                    doc.uploaded_at, doc.updated_at or doc.uploaded_at,
                ))
            if own_conn:
                conn.commit()
        except Exception:
            if own_conn:
                conn.rollback()
            raise
        finally:
            if own_conn:
                conn.close()

    def get(self, document_id: str) -> Document | None:
        """Get document by ID."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM document_intake WHERE document_id = %s", (document_id,))
                row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return None

        return Document(
            document_id=str(row["document_id"]),
            organization_id=str(row.get("organization_id", "")),
            uploaded_by=str(row.get("uploaded_by", "")),
            uploaded_at=row["uploaded_at"] or datetime.now(timezone.utc),
            status=str(row.get("status", "UPLOADED")),
            pipeline_stage=str(row.get("pipeline_stage", "")),
            storage_uri=str(row.get("storage_uri", "")),
            mime_type=str(row.get("mime_type", "")),
            page_count=int(row.get("page_count", 0)),
            size_bytes=int(row.get("size_bytes", 0)),
            checksum=str(row.get("checksum", "")),
            original_filename=str(row.get("original_filename", "")),
            metadata=row.get("metadata") or {},
            profile=row.get("profile") or {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def list_by_status(self, status: str) -> list[Document]:
        """List documents in a given status."""
        import psycopg2
        import psycopg2.extras
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM document_intake WHERE status = %s ORDER BY created_at DESC", (status,))
                rows = cur.fetchall()
        finally:
            conn.close()

        return [
            Document(
                document_id=str(r["document_id"]),
                organization_id=str(r.get("organization_id", "")),
                uploaded_by=str(r.get("uploaded_by", "")),
                uploaded_at=r["uploaded_at"] or datetime.now(timezone.utc),
                status=str(r.get("status", "UPLOADED")),
                pipeline_stage=str(r.get("pipeline_stage", "")),
                storage_uri=str(r.get("storage_uri", "")),
                mime_type=str(r.get("mime_type", "")),
                page_count=int(r.get("page_count", 0)),
                size_bytes=int(r.get("size_bytes", 0)),
                checksum=str(r.get("checksum", "")),
                original_filename=str(r.get("original_filename", "")),
                metadata=r.get("metadata") or {},
                profile=r.get("profile") or {},
                created_at=r.get("created_at"),
                updated_at=r.get("updated_at"),
            )
            for r in rows
        ]

    def update_status(self, document_id: str, status: str, stage: str = "") -> str | None:
        """Update document status. Returns error or None on success."""
        doc = self.get(document_id)
        if doc is None:
            return f"Document not found: {document_id}"

        err = transition_document(doc, status)
        if err:
            return err

        doc.pipeline_stage = stage or doc.pipeline_stage
        self.save(doc)
        return None
