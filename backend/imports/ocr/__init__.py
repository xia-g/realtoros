"""OCR Classifier — classify documents into categories.

Categories: invoice, receipt, contract, act, payment_order, other.
No posting creation — only classification.
Supports manual override + versioning + reclassification.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass
class ClassificationResult:
    document_id: str
    doc_type: str
    confidence: float
    evidence: list[str]
    classifier_version: str = "1.0.0"
    manual_override: bool = False

class Classifier:
    VERSION = "1.0.0"
    CATEGORIES = ["invoice", "receipt", "contract", "act", "payment_order", "other"]

    @staticmethod
    def classify(ocr_text: str, filename: str | None = None) -> ClassificationResult:
        evidence: list[str] = []
        text_lower = ocr_text.lower() if ocr_text else ""
        name_lower = filename.lower() if filename else ""

        # Rule-based classification
        if any(w in text_lower or w in name_lower for w in ["счет-фактура", "invoice", "счет на оплату", "инвойс"]):
            doc_type = "invoice"
            evidence.append("Keywords: счет-фактура/invoice")
        elif any(w in text_lower or w in name_lower for w in ["чек", "receipt", "кассовый чек", "фискальный"]):
            doc_type = "receipt"
            evidence.append("Keywords: чек/receipt")
        elif any(w in text_lower or w in name_lower for w in ["договор", "contract", "соглашение", "контракт"]):
            doc_type = "contract"
            evidence.append("Keywords: договор/contract")
        elif any(w in text_lower or w in name_lower for w in ["акт", "act", "акт выполненных работ", "certificate"]):
            doc_type = "act"
            evidence.append("Keywords: акт/act")
        elif any(w in text_lower or w in name_lower for w in ["платеж", "payment", "платежное поручение"]):
            doc_type = "payment_order"
            evidence.append("Keywords: платеж/payment")
        else:
            doc_type = "other"
            evidence.append("No matching keywords found")

        confidence = 0.9 if doc_type != "other" else 0.5
        return ClassificationResult(
            document_id=str(uuid.uuid4()),
            doc_type=doc_type,
            confidence=confidence,
            evidence=evidence,
            classifier_version=Classifier.VERSION,
        )

    @staticmethod
    async def reclassify(document_id: str, new_type: str, reason: str) -> ClassificationResult:
        """Manual override — reclassify a document."""
        if new_type not in Classifier.CATEGORIES:
            raise ValueError(f"Invalid category: {new_type}")
        return ClassificationResult(
            document_id=document_id,
            doc_type=new_type,
            confidence=1.0,
            evidence=[f"Manual override: {reason}"],
            classifier_version=Classifier.VERSION,
            manual_override=True,
        )
