"""OCR Step — calls existing OCRNode (port 8001)."""
from __future__ import annotations

import os
import httpx
from datetime import datetime

from backend.services.processing.models import PipelineRun, PipelineStep, OCRResult, QualityResult
from backend.services.processing.storage import PipelineRepository

# Quality thresholds
CONFIDENCE_GOOD = 0.90
CONFIDENCE_REVIEW = 0.70


def execute_ocr_step(
    pipeline: PipelineRun,
    step: PipelineStep,
    repo: PipelineRepository,
    ocr_url: str = "http://127.0.0.1:8001",
) -> tuple[bool, dict | str]:
    """Execute OCR step: call OCRNode, assess quality.

    Args:
        pipeline: Current pipeline run.
        step: Step record (will be updated).
        repo: Pipeline repository.
        ocr_url: OCRNode service URL.

    Returns:
        Tuple of (success, result_dict_or_error_message).
    """
    # Get document
    from backend.services.document_lifecycle import DocumentRepository
    from backend.config import settings

    doc_repo = DocumentRepository(dsn=settings.DATABASE_SYNC_URL)
    doc = doc_repo.get(pipeline.document_id)
    if doc is None:
        return False, f"Document not found: {pipeline.document_id}"

    storage_path = doc.storage_uri
    if not storage_path or not os.path.exists(storage_path):
        return False, f"File not found: {storage_path}"

    # Call OCRNode — async job API
    try:
        with open(storage_path, "rb") as f:
            files = {"file": (doc.original_filename or "document.pdf", f, doc.mime_type or "application/pdf")}
            data = {"lang": "rus+eng"}
            # Submit job
            resp = httpx.post(f"{ocr_url}/api/v1/jobs", files=files, data=data, timeout=30)

        if resp.status_code not in (200, 202):
            return False, f"OCRNode submit returned {resp.status_code}: {resp.text[:500]}"

        job_data = resp.json()
        job_id = job_data.get("job_id") or job_data.get("id")
        if not job_id:
            return False, f"OCRNode did not return job_id: {resp.text[:300]}"

        # Poll job until completion
        max_polls = 40
        for i in range(max_polls):
            import time
            time.sleep(3)
            poll_resp = httpx.get(f"{ocr_url}/api/v1/jobs/{job_id}", timeout=30)
            if poll_resp.status_code != 200:
                if i >= 3:
                    return False, f"OCRNode poll returned {poll_resp.status_code}: {poll_resp.text[:300]}"
                continue

            poll_data = poll_resp.json()
            status = poll_data.get("status", "").lower()

            if status in ("completed", "ready", "done", "need_review"):
                ocr_data = poll_data.get("result") or poll_data.get("normalized_document") or poll_data
                # Flatten OCRNode response: top-level fields may hold key data
                if "normalized_document" in poll_data and isinstance(poll_data["normalized_document"], dict):
                    nd = poll_data["normalized_document"]
                    if not ocr_data.get("raw_text") and nd.get("raw_text"):
                        ocr_data["raw_text"] = nd["raw_text"]
                    if not ocr_data.get("confidence") and nd.get("confidence"):
                        ocr_data["ocr_confidence"] = nd["confidence"].get("ocr_confidence", 0)
                    if not ocr_data.get("page_count") and nd.get("pages"):
                        ocr_data["page_count"] = nd["pages"]
                    if poll_data.get("document_type"):
                        ocr_data["document_type"] = poll_data["document_type"]
                break
            elif status in ("failed", "error"):
                err_msg = poll_data.get("error") or poll_data.get("message") or "Unknown OCR error"
                return False, f"OCR failed: {err_msg}"
            elif status in ("need_review", "pending", "processing"):
                continue
        else:
            return False, f"OCR job {job_id} did not complete after {max_polls * 3}s"
    except Exception as e:
        return False, f"OCRNode call failed: {e}"

    raw_text = ocr_data.get("text") or ocr_data.get("raw_text", "")
    # Handle confidence: can be float or dict from OCRNode
    raw_conf = ocr_data.get("ocr_confidence", ocr_data.get("confidence", 0.0))
    if isinstance(raw_conf, dict):
        raw_conf = raw_conf.get("ocr_confidence", raw_conf.get("overall_confidence", 0.0))
    confidence = float(raw_conf) if raw_conf else 0.0
    language = str(ocr_data.get("language", ""))
    page_count = int(ocr_data.get("pages", ocr_data.get("page_count", 0)))

    ocr_result = OCRResult(
        raw_text=raw_text,
        confidence=confidence,
        language=language,
        page_count=page_count,
    )

    # Quality assessment
    quality = assess_quality(ocr_result, doc.page_count)
    step.result = {
        "ocr": {
            "raw_text": raw_text,
            "raw_text_preview": raw_text[:500],
            "confidence": confidence,
            "language": language,
            "page_count": page_count,
        },
        "quality": {
            "overall_score": quality.overall_score,
            "needs_review": quality.needs_review,
            "warnings": quality.warnings,
        },
    }

    if quality.needs_review:
        # Mark pipeline as NEEDS_REVIEW
        repo.update_pipeline_status(pipeline.pipeline_id, "NEEDS_REVIEW")
        return True, step.result

    return True, step.result


def assess_quality(ocr_result: OCRResult, expected_pages: int = 0) -> QualityResult:
    """Assess OCR quality against thresholds."""
    warnings: list[str] = []
    confidence = ocr_result.confidence

    if confidence < CONFIDENCE_REVIEW:
        warnings.append(f"OCR confidence too low: {confidence:.2f} (threshold: {CONFIDENCE_REVIEW})")
    elif confidence < CONFIDENCE_GOOD:
        warnings.append(f"OCR confidence below ideal: {confidence:.2f}")

    if expected_pages > 0 and ocr_result.page_count != expected_pages:
        warnings.append(f"Page count mismatch: expected {expected_pages}, got {ocr_result.page_count}")

    overall = confidence * (0.9 if warnings else 1.0)

    return QualityResult(
        ocr_confidence=confidence,
        overall_score=min(1.0, max(0.0, overall)),
        needs_review=confidence < CONFIDENCE_REVIEW,
        warnings=warnings,
    )
