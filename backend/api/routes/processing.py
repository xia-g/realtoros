"""Document Processing Pipeline API — Epic 1 / Stream 2.

Endpoints:
  POST /documents/{id}/process              — Start pipeline
  GET  /processing/pipelines/{pipeline_id}  — Pipeline status + steps
  POST /processing/pipelines/{pipeline_id}/retry — Retry failed pipeline

Product Layer, not Platform.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.services.processing.pipeline import PipelineOrchestrator
from backend.services.processing.steps.ocr_step import execute_ocr_step
from backend.services.processing.steps.classification_step import execute_classification_step
from backend.services.processing.steps.extraction_step import execute_extraction_step
from backend.services.processing.steps.knowledge_step import execute_knowledge_step
from backend.services.document_lifecycle import DocumentRepository, transition_document

router = APIRouter(prefix="/processing", tags=["Document Processing"])


def _get_orch(request: Request) -> PipelineOrchestrator:
    from backend.config import settings
    return PipelineOrchestrator(settings.DATABASE_SYNC_URL)


def _get_doc_repo(request: Request):
    from backend.config import settings
    return DocumentRepository(settings.DATABASE_SYNC_URL)


@router.post("/pipelines/start/{document_id}")
async def start_pipeline(document_id: str, request: Request):
    """Start document processing pipeline.

    Document must be in ACCEPTED status.
    Returns pipeline_id for status polling.
    """
    doc_repo = _get_doc_repo(request)
    doc = doc_repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    if doc.status != "ACCEPTED":
        raise HTTPException(
            status_code=400,
            detail=f"Document must be ACCEPTED to process (current: {doc.status})",
        )

    # Transition to PROCESSING
    err = transition_document(doc, "PROCESSING")
    if err:
        raise HTTPException(status_code=400, detail=err)
    doc.pipeline_stage = "processing"
    doc_repo.save(doc)

    # Create pipeline
    orch = _get_orch(request)
    pipeline = orch.create_pipeline(document_id)

    # Execute synchronously for v1
    step_executors = {
        "ocr": execute_ocr_step,
        "classification": execute_classification_step,
        "extraction": execute_extraction_step,
        "knowledge": execute_knowledge_step,
    }

    try:
        result = orch.run_pipeline(pipeline.pipeline_id, step_executors)

        # Update document status based on pipeline result
        if result.status == "COMPLETED":
            doc.status = "ANALYZED"
            doc.pipeline_stage = "completed"
            # Update profile from pipeline results
            steps = orch.get_steps(pipeline.pipeline_id)
            for s in steps:
                if s.step_type == "classification" and s.result:
                    doc.profile["document_type"] = s.result.get("document_type", "unknown")
                    doc.profile["classification_confidence"] = s.result.get("confidence", 0)
                if s.step_type == "extraction" and s.result:
                    doc.profile["fields"] = s.result.get("fields", {})
                    doc.profile["extraction_confidence"] = s.result.get("confidence", 0)
                    # v2 structured profile — make primary data source
                    extraction_profile = s.result.get("profile")
                    if extraction_profile:
                        doc.profile["profile"] = extraction_profile
                        doc.profile["profile_version"] = extraction_profile.get("profile_version", "1.0")
                        # Also enrich top-level fields from profile for backward compat
                        sections = extraction_profile.get("sections", {})
                        if sections.get("identification"):
                            doc.profile["contract_number"] = sections["identification"].get("contract_number")
                        if sections.get("parties", {}).get("seller"):
                            doc.profile["seller_name"] = sections["parties"]["seller"].get("name")
                        if sections.get("parties", {}).get("buyer"):
                            doc.profile["buyer_name"] = sections["parties"]["buyer"].get("name")
                        if sections.get("financial_terms", {}).get("total_price"):
                            doc.profile["total_price"] = sections["financial_terms"]["total_price"].get("value")
                if s.step_type == "ocr" and s.result:
                    doc.profile["ocr_confidence"] = s.result.get("ocr", {}).get("confidence", 0)
        elif result.status == "NEEDS_REVIEW":
            err = transition_document(doc, "NEEDS_REVIEW")
            if err:
                doc.status = "NEEDS_REVIEW"
            doc.pipeline_stage = "needs_review"
        elif result.status == "FAILED":
            doc.status = "FAILED"
            doc.pipeline_stage = "failed"

        doc_repo.save(doc)

    except Exception as e:
        doc.status = "FAILED"
        doc.pipeline_stage = "pipeline_error"
        doc_repo.save(doc)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")

    return {
        "pipeline_id": pipeline.pipeline_id,
        "document_id": document_id,
        "status": result.status,
        "document_status": doc.status,
    }


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str, request: Request):
    """Get pipeline status with step details."""
    orch = _get_orch(request)
    pipeline = orch.get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    steps = orch.get_steps(pipeline_id)

    return {
        "pipeline_id": pipeline.pipeline_id,
        "document_id": pipeline.document_id,
        "status": pipeline.status,
        "created_at": pipeline.created_at.isoformat() if pipeline.created_at else None,
        "completed_at": pipeline.completed_at.isoformat() if pipeline.completed_at else None,
        "steps": [
            {
                "step_type": s.step_type,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "result": s.result,
                "error": s.error,
            }
            for s in steps
        ],
    }


@router.post("/pipelines/{pipeline_id}/retry")
async def retry_pipeline(pipeline_id: str, request: Request):
    """Retry a failed pipeline."""
    from backend.services.processing.models import transition_pipeline

    orch = _get_orch(request)
    pipeline = orch.get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Pipeline not found: {pipeline_id}")

    if pipeline.status != "FAILED":
        raise HTTPException(status_code=400, detail=f"Can only retry FAILED pipelines (current: {pipeline.status})")

    # Reset to PENDING
    err = transition_pipeline(pipeline, "PENDING")
    if err:
        raise HTTPException(status_code=400, detail=err)

    from backend.services.processing.storage import PipelineRepository
    from backend.config import settings
    repo = PipelineRepository(settings.DATABASE_SYNC_URL)
    repo.save_pipeline(pipeline)

    # Reset failed steps
    steps = repo.get_steps(pipeline_id)
    for step in steps:
        if step.status == "FAILED":
            step.status = "PENDING"
            step.error = ""
            step.result = {}
            step.completed_at = None
            repo.save_step(step)

    return {"pipeline_id": pipeline_id, "status": "PENDING"}
