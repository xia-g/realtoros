"""
API — Replay.

POST /api/v1/replay/{document_id}

Повторный прогон документа через pipeline.
Не изменяет исходный normalized_document.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException

from contracts import NormalizedDocument, DocumentStatus
from application.workflows.accounting_pipeline import AccountingPipeline, PipelineResult


class ReplayMode(str, Enum):
    """Режимы replay."""
    FULL = "full"               # enrich → validate → map → approve → post
    FROM_ENRICHMENT = "from_enrichment"  # начиная с enrich
    FROM_MAPPING = "from_mapping"        # начиная с map
    FROM_POSTING = "from_posting"        # только posting


class DocumentStore(Protocol):
    """Хранилище normalized_document для replay."""
    async def get_by_id(self, doc_id: str) -> NormalizedDocument | None: ...
    async def get_accounting_doc(self, doc_id: str) -> dict | None: ...


router = APIRouter(prefix="/api/v1/replay", tags=["Replay"])


@router.post("/{document_id}")
async def replay_document(
    document_id: str,
    mode: ReplayMode = ReplayMode.FULL,
    store: DocumentStore = None,  # injected
    pipeline: AccountingPipeline = None,  # injected
) -> dict[str, Any]:
    """Повторный прогон документа через pipeline.

    - Не меняет исходный normalized_document
    - Идемпотентен: повторный POST с тем же mode даёт тот же результат
    - Disposable: можно удалить результат и replay ещё раз
    """
    if not store or not pipeline:
        raise HTTPException(status_code=503, detail="Replay service not available")

    # 1. Load document
    doc = await store.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    result: PipelineResult | None = None

    # 2. Execute by mode
    if mode == ReplayMode.FULL:
        result = await pipeline.run(doc)
        if result.success and result.accounting:
            post_result = await pipeline.execute_posting(result.accounting)
            result = PipelineResult(
                success=post_result.success,
                enriched=result.enriched,
                validation=result.validation,
                accounting=post_result.accounting or result.accounting,
                journal_entry=post_result.journal_entry,
                errors=result.errors + post_result.errors,
                warnings=result.warnings + post_result.warnings,
            )

    elif mode == ReplayMode.FROM_ENRICHMENT:
        result = await pipeline.run(doc)

    elif mode == ReplayMode.FROM_MAPPING:
        # Load accounting_document from store, re-post
        acc_data = await store.get_accounting_doc(document_id)
        if not acc_data:
            raise HTTPException(status_code=400, detail="No accounting document to replay")
        from contracts import AccountingDocument
        acc = AccountingDocument(**acc_data)
        result = await pipeline.execute_posting(acc)

    elif mode == ReplayMode.FROM_POSTING:
        acc_data = await store.get_accounting_doc(document_id)
        if not acc_data:
            raise HTTPException(status_code=400, detail="No accounting document to replay")
        from contracts import AccountingDocument, PostingResult
        acc = AccountingDocument(**acc_data)
        approved = AccountingDocument(**{**dict(acc), "status": DocumentStatus.APPROVED})
        post_result = await pipeline._posting.post(approved)
        result = PipelineResult(
            success=post_result.result == PostingResult.POSTED,
            journal_entry=post_result.entry,
        )

    if not result:
        raise HTTPException(status_code=500, detail="Replay failed")

    return {
        "document_id": document_id,
        "mode": mode.value,
        "success": result.success,
        "errors": result.errors,
        "warnings": result.warnings,
        "has_journal_entry": result.journal_entry is not None,
    }
