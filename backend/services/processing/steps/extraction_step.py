"""Extraction Step — type-specific extraction from OCR text.

v1: flat regex patterns (backward compatible for non-contract docs)
v2: structured ContractProfile for contract documents
"""
from __future__ import annotations

import re

from backend.services.processing.models import PipelineRun, PipelineStep
from backend.services.processing.storage import PipelineRepository

# v1 patterns — kept for backward compatibility with non-contract documents
FIELD_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "supplier": [
        (r"(?:поставщик|supplier|продавец|seller)[:\s]+(.+)", 0.9),
        (r"(?:организация|company|фирма)[:\s]+(.+)", 0.7),
    ],
    "customer": [
        (r"(?:покупатель|customer|buyer|заказчик)[:\s]+(.+)", 0.9),
        (r"(?:плательщик|payer)[:\s]+(.+)", 0.7),
    ],
    "amount": [
        (r"(?:сумма|total|amount|итого|всего)[:\s]*([\d\s.,]+)", 0.9),
        (r"(?:к оплате|payable|to pay)[:\s]*([\d\s.,]+)", 0.8),
    ],
    "vat": [
        (r"(?:ндс|vat|налог[:\s]*[нн]дс)[:\s]*([\d\s.,]+)", 0.9),
        (r"(?:tax|в т\.ч\. ндс)[:\s]*([\d\s.,]+)", 0.8),
    ],
    "invoice_number": [
        (r"(?:№|номер|invoice\s+#?|счет\s+№?)[:\s]*(\S+)", 0.9),
        (r"(?:документ|document)[:\s]*№?[:\s]*(\S+)", 0.6),
    ],
    "date": [
        (r"(\d{2}[./]\d{2}[./]\d{4})", 0.8),
        (r"(\d{4}[-]\d{2}[-]\d{2})", 0.8),
    ],
    "contract_number": [
        (r"(?:договор|contract|соглашение)[:\s]*№?[:\s]*(\S+)", 0.9),
    ],
    "iban": [
        (r"[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}", 0.9),
    ],
}

# Required fields per document type
TYPE_FIELDS: dict[str, list[str]] = {
    "invoice": ["supplier", "amount", "vat", "invoice_number", "date"],
    "contract": ["supplier", "customer", "date", "contract_number"],
    "act": ["supplier", "customer", "date", "amount"],
    "bank_statement": ["date"],
    "receipt": ["amount", "date"],
    "passport": ["date"],
    "power_of_attorney": ["date"],
}


def extract_fields(raw_text: str, document_type: str) -> dict:
    """v1 extraction — flat regex patterns. Returns dict with fields, confidence, warnings."""
    result: dict[str, str] = {}
    warnings: list[str] = []

    for field_name, patterns in FIELD_PATTERNS.items():
        for pattern, _ in patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            if matches:
                value = matches[0].strip()
                if value and len(value) < 200:
                    result[field_name] = value
                    break

    required = TYPE_FIELDS.get(document_type, [])
    found_required = sum(1 for f in required if f in result)
    missing = [f for f in required if f not in result]
    if missing:
        warnings.append(f"Missing required fields for {document_type}: {', '.join(missing)}")

    confidence = found_required / len(required) if required else 0.5

    return {"fields": result, "confidence": confidence, "warnings": warnings}


def extract_fields_v2(raw_text: str, doc_type: str) -> dict:
    """v2 extraction — structured profile for contracts, v1 fallback for others.

    Returns dict with fields (v1 compat) + profile (v2 structured) if applicable.
    """
    v1_result = extract_fields(raw_text, doc_type)

    if doc_type == "contract":
        try:
            from backend.services.processing.extraction.contract_extractor import extract_contract_profile
            profile = extract_contract_profile(raw_text)
            profile_dict = profile.to_dict()

            # Merge: v1 fields on top level (backward compat)
            return {
                "document_type": doc_type,
                "fields": v1_result["fields"],
                "profile": profile_dict,
                "confidence": profile.confidence,
                "warnings": [w.message for w in profile.metadata.warnings],
            }
        except ImportError:
            # Extraction module not available — fall back to v1
            return {
                "document_type": doc_type,
                "fields": v1_result["fields"],
                "confidence": v1_result["confidence"],
                "warnings": v1_result["warnings"] + ["Extraction v2 unavailable, using v1"],
            }

    # Non-contract: v1 only
    return {
        "document_type": doc_type,
        "fields": v1_result["fields"],
        "confidence": v1_result["confidence"],
        "warnings": v1_result["warnings"],
    }


def execute_extraction_step(
    pipeline: PipelineRun,
    step: PipelineStep,
    repo: PipelineRepository,
) -> tuple[bool, dict | str]:
    """Execute extraction step on classified document."""
    steps = repo.get_steps(pipeline.pipeline_id)

    ocr_step = next((s for s in steps if s.step_type == "ocr"), None)
    if not ocr_step or not ocr_step.result:
        return False, "No OCR result for extraction"

    raw_text = ocr_step.result.get("ocr", {}).get("raw_text", "")
    if not raw_text:
        raw_text = ocr_step.result.get("ocr", {}).get("raw_text_preview", "")

    class_step = next((s for s in steps if s.step_type == "classification"), None)
    doc_type = "unknown"
    if class_step and class_step.result:
        doc_type = class_step.result.get("document_type", "unknown")

    result = extract_fields_v2(raw_text, doc_type)

    return True, result
