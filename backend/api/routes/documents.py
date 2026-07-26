"""Document management API endpoints.

Sync lifecycle operations via DocumentRepository (psycopg2).
"""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from backend.config import settings
from backend.services.document_lifecycle import (
    Document,
    DocumentRepository,
    mark_document_ready,
    transition_document,
    VALID_TRANSITIONS,
)

router = APIRouter()

UPLOAD_DIR = os.path.join(settings.DATA_DIR, "uploads") if hasattr(settings, "DATA_DIR") else "/tmp/realtoros-uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get document details via sync DocumentRepository."""
    repo = _get_repo()
    doc = repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_doc(doc)


# ─── Sync lifecycle endpoints (psycopg2 DocumentRepository) ──────


def _get_repo() -> DocumentRepository:
    return DocumentRepository(dsn=settings.DATABASE_SYNC_URL)


def _serialize_doc(doc: Document) -> dict:
    return {
        "document_id": doc.document_id,
        "organization_id": doc.organization_id,
        "uploaded_by": doc.uploaded_by,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "status": doc.status,
        "pipeline_stage": doc.pipeline_stage,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "page_count": doc.page_count,
        "size_bytes": doc.size_bytes,
        "checksum": doc.checksum,
        "metadata": doc.metadata,
        "profile": doc.profile,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    organization_id: str = Form(""),
):
    """Upload a document file, create Document record.

    Lifecycle: UPLOADED
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    doc_id = str(uuid.uuid4())
    checksum = hashlib.sha256(content).hexdigest()
    mime = file.content_type or "application/octet-stream"

    ext = os.path.splitext(file.filename or "unnamed")[1] or ""
    storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    with open(storage_path, "wb") as f:
        f.write(content)

    doc = Document(
        document_id=doc_id,
        organization_id=organization_id,
        uploaded_by=str(uuid.UUID(int=0)),
        uploaded_at=datetime.now(timezone.utc),
        status="UPLOADED",
        pipeline_stage="intake",
        storage_uri=storage_path,
        mime_type=mime,
        page_count=0,
        size_bytes=len(content),
        checksum=checksum,
        original_filename=file.filename or "unnamed",
        metadata={},
        profile={},
    )

    repo = _get_repo()
    repo.save(doc)

    return _serialize_doc(doc)


@router.get("/{document_id}/status")
async def get_document_status(document_id: str):
    """Get document lifecycle status and available transitions."""
    repo = _get_repo()
    doc = repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    allowed = VALID_TRANSITIONS.get(doc.status, [])

    return {
        "document_id": doc.document_id,
        "status": doc.status,
        "pipeline_stage": doc.pipeline_stage,
        "allowed_transitions": allowed,
        "is_terminal": doc.status in ("ARCHIVED", "REJECTED"),
    }


@router.post("/{document_id}/transition")
async def transition_document_status(
    document_id: str,
    body: dict,
):
    """Transition document to a new lifecycle state.

    Validates the transition. Returns updated document.
    JSON body: {"target_status": "...", "pipeline_stage": "..."}
    """
    target = body.get("target_status", "")
    stage = body.get("pipeline_stage", "")

    repo = _get_repo()
    doc = repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    err = transition_document(doc, target)
    if err:
        raise HTTPException(status_code=400, detail=err)

    doc.pipeline_stage = stage or doc.pipeline_stage
    repo.save(doc)

    return _serialize_doc(doc)


@router.get("/list")
async def list_documents_sync(
    status: str = Query(None, description="Filter by lifecycle status"),
    limit: int = Query(50, ge=1, le=200),
):
    """List documents, optionally filtered by status."""
    repo = _get_repo()
    if status:
        docs = repo.list_by_status(status)
    else:
        import psycopg2
        import psycopg2.extras
        conn = repo._connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM document_intake ORDER BY created_at DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        finally:
            conn.close()
        docs = [
            Document(
                document_id=str(r["document_id"]),
                organization_id=r.get("organization_id", ""),
                uploaded_by=r.get("uploaded_by", ""),
                uploaded_at=r.get("uploaded_at"),
                status=r.get("status", "UPLOADED"),
                pipeline_stage=r.get("pipeline_stage", ""),
                original_filename=r.get("original_filename", ""),
                mime_type=r.get("mime_type", ""),
                page_count=r.get("page_count", 0),
                size_bytes=r.get("size_bytes", 0),
                checksum=r.get("checksum", ""),
                metadata=r.get("metadata") or {},
                profile=r.get("profile") or {},
                created_at=r.get("created_at") or r.get("uploaded_at"),
                updated_at=r.get("updated_at") or r.get("uploaded_at"),
            )
            for r in rows
        ]

    return {
        "documents": [_serialize_doc(d) for d in docs],
        "total": len(docs),
    }


@router.post("/{document_id}/mark-ready")
async def mark_document_ready_endpoint(document_id: str, request: Request):
    """Mark a document as READY.

    Document must be in ANALYZED or NEEDS_REVIEW state.
    Emits EVENT_DOCUMENT_READY domain event.
    Returns updated document with event_id and event_type.
    """
    repo = _get_repo()
    doc = repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    from backend.core.context import get_request_context
    ctx = get_request_context()
    actor_id = ctx.user_id if ctx and ctx.user_id else "system"

    err, event = mark_document_ready(doc, actor_id=actor_id)
    if err:
        # 409 Conflict for idempotency (already READY)
        if "already in READY" in err:
            raise HTTPException(status_code=409, detail=err)
        # 422 Unprocessable Entity for invalid transitions
        raise HTTPException(status_code=422, detail=err)

    repo.save(doc)

    result = _serialize_doc(doc)
    result["event_id"] = str(event.entity_id) if event else None
    result["event_type"] = event.event_type if event else None
    return result
