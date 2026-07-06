"""
Document → Deal Lifecycle v1.6.

POST /api/v1/documents/{document_id}/promote-to-deal
GET  /api/v1/deals/{deal_id}/requirements
GET  /api/v1/deals/{deal_id}/timeline

Pipeline:
  idempotency check → confidence gate → document role → deal create
  → link document → requirements → events → accounting intent → response
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException
import asyncpg

router = APIRouter(prefix="/documents", tags=["Document→Deal"])

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
DSN = DSN.replace("+asyncpg", "")


class DocumentRole(str, Enum):
    SALE_CONTRACT = "sale_contract"
    TRANSFER_ACT = "transfer_act"
    EGRN_EXTRACT = "egrn_extract"
    PAYMENT_ORDER = "payment_order"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CERTIFICATE = "certificate"
    CADASTRAL = "cadastral"
    ADVANCE_REPORT = "advance_report"
    RECONCILIATION = "reconciliation"
    UNKNOWN = "unknown"


class RequirementStatus(str, Enum):
    REQUESTED = "requested"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    WAIVED = "waived"


class ConfidenceLevel(str, Enum):
    AUTO_PROMOTE = "auto_promote"
    REVIEW_REQUIRED = "review_required"
    MANUAL_CLASSIFICATION = "manual_classification"


class AccountingIntent(str, Enum):
    POSTABLE = "postable"
    NON_POSTABLE = "non_postable"


class LifecycleStage(str, Enum):
    DEAL_CANDIDATE = "deal_candidate"
    DOCUMENT_REVIEW = "document_review"
    READY_FOR_ACCOUNTING = "ready_for_accounting"
    COMPLETED = "completed"


DOC_TYPE_TO_ROLE: dict[str, str] = {
    "contract": "sale_contract",
    "municipal_contract": "sale_contract",
    "invoice": "invoice",
    "receipt": "receipt",
    "act": "transfer_act",
    "payment_order": "payment_order",
    "property_doc": "egrn_extract",
    "bank_statement": "reconciliation",
}

# Reverse: document_role → requirement document_type
DOC_ROLE_TO_REQ: dict[str, str] = {
    "sale_contract": "dkp",
    "transfer_act": "acceptance_act",
    "egrn_extract": "egrn_extract",
    "payment_order": "payment_order",
    "invoice": "invoice",
    "receipt": "receipt",
    "passport": "passport_seller",
    "certificate": "certificate",
    "cadastral": "cadastral_passport",
    "reconciliation": "reconciliation_act",
}

DOC_TO_DEAL_TYPE: dict[str, str] = {
    "contract": "purchase", "municipal_contract": "purchase",
    "invoice": "payment", "receipt": "expense",
    "act": "purchase", "payment_order": "payment",
    "property_doc": "registration", "bank_statement": "payment",
}

POSTABLE_TYPES = {"payment_order", "invoice", "receipt"}


class ConfidenceGate:
    @staticmethod
    def evaluate(confidence: float) -> ConfidenceLevel:
        if confidence >= 0.90:
            return ConfidenceLevel.AUTO_PROMOTE
        elif confidence >= 0.70:
            return ConfidenceLevel.REVIEW_REQUIRED
        return ConfidenceLevel.MANUAL_CLASSIFICATION


class AccountingIntentClassifier:
    @staticmethod
    def classify(doc_type: str) -> AccountingIntent:
        return AccountingIntent.POSTABLE if doc_type.lower() in POSTABLE_TYPES else AccountingIntent.NON_POSTABLE


class DealEventService:
    @staticmethod
    async def emit(conn, deal_id: str, event_type: str, title: str, metadata: dict | None = None):
        await conn.execute(
            """INSERT INTO deal_timeline_events
               (id, deal_id, event_type, source_component, title, description, metadata, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            str(uuid.uuid4()), deal_id, event_type, "document_pipeline",
            title[:200], title, json.dumps(metadata or {}), datetime.utcnow(),
        )


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=DSN, min_size=1, max_size=3)


# ── POST /documents/{id}/promote-to-deal ──

@router.post("/{document_id}/promote-to-deal")
async def promote_to_deal(document_id: str):
    """Promote OCR document to deal. Idempotent, confidence-gated."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            intake = await conn.fetchrow(
                """SELECT id, company_id, file_name, classification, confidence,
                          extracted_fields, status, promoted_deal_id, final_type
                   FROM accounting.document_intake WHERE id = $1""", document_id
            )
            if not intake:
                raise HTTPException(status_code=404, detail="Document intake not found")

            # Idempotency
            if intake["promoted_deal_id"]:
                existing = await conn.fetchrow("SELECT id, status, lifecycle_stage FROM public.deals WHERE id = $1", intake["promoted_deal_id"])
                if existing:
                    return {"deal_id": str(existing["id"]), "status": "existing", "deal_stage": existing["lifecycle_stage"] or "deal_candidate"}

            doc_type = intake["classification"] or "unknown"
            confidence = intake["confidence"] or 0.0
            company_id = intake["company_id"]
            file_name = intake["file_name"]

            # Confidence gate
            conf_level = ConfidenceGate.evaluate(confidence)
            if conf_level == ConfidenceLevel.MANUAL_CLASSIFICATION:
                raise HTTPException(status_code=400, detail=f"low confidence ({confidence:.2f})")
            if conf_level == ConfidenceLevel.REVIEW_REQUIRED:
                return {"status": "review_required", "document_id": document_id, "confidence": round(confidence, 2), "classification": doc_type}

            # 4. Parse fields and parties from extracted_fields JSON
            fields = {}
            parties = []
            if intake["extracted_fields"]:
                raw = json.loads(intake["extracted_fields"]) if isinstance(intake["extracted_fields"], str) else intake["extracted_fields"]
                fields = raw
                # Try to extract parties from fields if stored
                if isinstance(raw, dict):
                    parties = raw.get("parties", []) or raw.get("party", []) or []

            deal_type = DOC_TO_DEAL_TYPE.get(doc_type, "other")
            doc_role = DOC_TYPE_TO_ROLE.get(doc_type, "unknown")

            # Extract counterparty INN from fields for passport_seller logic
            counterparty_inn = ""
            if isinstance(fields, dict):
                counterparty_inn = fields.get("vat_number", [""])[0] if isinstance(fields.get("vat_number"), list) else \
                                   fields.get("inn", [""])[0] if isinstance(fields.get("inn"), list) else \
                                   fields.get("INN", [""])[0] if isinstance(fields.get("INN"), list) else ""

            # Create deal
            deal_id = str(uuid.uuid4())
            now = datetime.utcnow()
            price = 0.0
            if fields.get("amounts"):
                try: price = max(float(a) for a in fields["amounts"])
                except: pass

            counterparty = ""
            our_name = ""
            for p in parties:
                rel = p.get("relation", {})
                if rel.get("role") == "counterparty": counterparty = p.get("identity", {}).get("name", "")
                if rel.get("role") == "our_side": our_name = p.get("identity", {}).get("name", "")

            deal_title = f"{our_name + ' - ' if our_name else ''}{'Покупка' if deal_type == 'purchase' else 'Платёж'} - {counterparty[:100] if counterparty else file_name[:80]}"

            # Use first system user as created_by (deals FK references users)
            system_user_id = "5055acf6-e7f2-4b9a-82f7-f19eba6caff6"
            await conn.execute(
                """INSERT INTO public.deals (id, deal_type, status, lifecycle_stage, property_id, title, description,
                    price, price_currency, commission, deposit_amount, start_date, source, created_by, created_at, updated_at)
                   VALUES ($1, $2, 'initiated', $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $14)""",
                deal_id, deal_type, LifecycleStage.DEAL_CANDIDATE.value, None, deal_title[:200],
                f"Создан из: {file_name}", price, "RUB", 0.0, 0.0, date.today(), "ocr_ingestion",
                system_user_id, now
            )

            # Mark promoted
            await conn.execute("UPDATE accounting.document_intake SET promoted_deal_id=$1, confidence_auto_promoted=$2 WHERE id=$3",
                               deal_id, conf_level == ConfidenceLevel.AUTO_PROMOTE, document_id)

            # Create document record
            doc_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO public.documents (id, document_type, status, title, file_name, file_path, file_size,
                    mime_type, uploaded_by, deal_id, created_at, updated_at)
                   VALUES ($1, $2, 'received', $3, $4, $5, $6, $7, $8, $9, $10, $10)""",
                doc_id, doc_type, file_name[:200], file_name, f"/intake/{document_id}", 0, "application/octet-stream",
                system_user_id, deal_id, now
            )

            # 9. Link via deal_document_packages — find real requirement_id
            doc_req = await conn.fetchrow(
                "SELECT id FROM document_requirements WHERE deal_type = $1 AND document_type = $2 AND deleted_at IS NULL LIMIT 1",
                deal_type, DOC_ROLE_TO_REQ.get(doc_role, "")
            )
            req_id_for_doc = doc_req["id"] if doc_req else str(uuid.uuid4())
            pkg_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO deal_document_packages (id, deal_id, requirement_id, document_id, status, document_role,
                    verified, attached_at, requirement_status, created_at, updated_at)
                   VALUES ($1, $2, $3, $4, 'attached', $5, true, $6, 'verified', $7, $7)""",
                pkg_id, deal_id, req_id_for_doc, doc_id, doc_role, now, now
            )

            # 10. Create requirements for remaining docs — skip passport for legal entities
            skip_passport = bool(counterparty_inn) and len(counterparty_inn) >= 10
            reqs = await conn.fetch(
                "SELECT id, document_type, label, is_required, sort_order FROM document_requirements "
                "WHERE deal_type = $1 AND deleted_at IS NULL ORDER BY sort_order",
                deal_type
            )
            requirement_results = []
            for req in reqs:
                # Skip passport_seller when counterparty is a legal entity (has INN)
                if req["document_type"] == "passport_seller" and skip_passport:
                    continue
                # Check if requirement matches the attached document's role
                # Check if requirement matches the attached document's role
                # Use DOC_ROLE_TO_REQ reverse-mapping or direct comparison
                is_fulfilled = False
                for d_role_key, req_type in DOC_ROLE_TO_REQ.items():
                    if req_type == req["document_type"] and d_role_key == doc_role:
                        is_fulfilled = True
                        break
                status = RequirementStatus.VERIFIED if is_fulfilled else RequirementStatus.REQUESTED
                if not is_fulfilled:
                    req_role_val = DOC_ROLE_TO_REQ.get(doc_role, doc_role)
                    await conn.execute(
                        """INSERT INTO deal_document_packages (id, deal_id, requirement_id, document_id, status, document_role,
                            verified, requirement_status, created_at, updated_at)
                           VALUES ($1, $2, $3, NULL, 'pending', $4, false, $5, $6, $6)""",
                        str(uuid.uuid4()), deal_id, req["id"], req_role_val, status.value, now
                    )
                requirement_results.append({"requirement_id": str(req["id"]), "document_type": req["document_type"],
                    "label": req["label"], "is_required": req["is_required"], "status": status.value, "document_role": doc_role})

            # Events
            accounting_intent = AccountingIntentClassifier.classify(doc_type)
            await DealEventService.emit(conn, deal_id, "DEAL_CREATED", f"Сделка: {deal_title[:60]}")
            await DealEventService.emit(conn, deal_id, "DOCUMENT_ATTACHED", f"Документ: {file_name[:60]}", {"doc_id": doc_id, "doc_role": doc_role})
            await DealEventService.emit(conn, deal_id, "ACCOUNTING_INTENT_DETECTED", f"Назначение: {accounting_intent.value}", {"intent": accounting_intent.value})

            missing_count = sum(1 for r in requirement_results if r["status"] != "verified")
            return {"deal_id": deal_id, "status": "created", "deal_type": deal_type, "deal_title": deal_title[:200],
                "deal_stage": LifecycleStage.DEAL_CANDIDATE.value, "document_type": doc_type, "document_role": doc_role,
                "document_confidence": round(confidence, 2), "confidence_level": conf_level.value,
                "accounting_intent": accounting_intent.value, "auto_promoted": conf_level == ConfidenceLevel.AUTO_PROMOTE,
                "price": price, "counterparty": counterparty, "parties": parties,
                "document_requirements": requirement_results, "missing_count": missing_count}
    finally:
        await pool.close()


# ── GET /deals/{deal_id}/requirements ──

requirements_router = APIRouter(prefix="/deals", tags=["Deal Requirements"])

@requirements_router.get("/{deal_id}/requirements")
async def get_deal_requirements(deal_id: str):
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT dp.id, dp.requirement_id, dp.document_role, dp.requirement_status, dp.verified,
                          dp.document_id, dp.attached_at, r.label, r.document_type, r.is_required, r.sort_order
                   FROM deal_document_packages dp
                   LEFT JOIN document_requirements r ON r.id = dp.requirement_id
                   WHERE dp.deal_id = $1 AND dp.deleted_at IS NULL
                   ORDER BY r.sort_order""", deal_id
            )
            return [{"package_id": str(r["id"]), "requirement_id": str(r["requirement_id"]) if r["requirement_id"] else "",
                "document_role": r["document_role"], "status": r["requirement_status"], "verified": r["verified"],
                "document_id": str(r["document_id"]) if r["document_id"] else "", "label": r["label"],
                "document_type": r["document_type"], "is_required": r["is_required"],
                "attached_at": str(r["attached_at"]) if r["attached_at"] else ""} for r in rows]
    finally:
        await pool.close()


# ── GET /deals/{deal_id}/timeline ──

timeline_router = APIRouter(prefix="/deals", tags=["Deal Timeline"])

@timeline_router.get("/{deal_id}/timeline")
async def get_deal_timeline(deal_id: str):
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, event_type, title, description, metadata, created_at
                   FROM deal_timeline_events WHERE deal_id = $1
                   ORDER BY created_at DESC LIMIT 50""", deal_id
            )
            return [{"event_id": str(r["id"]), "event_type": r["event_type"], "title": r["title"],
                "description": r["description"], "metadata": r["metadata"],
                "created_at": str(r["created_at"])} for r in rows]
    finally:
        await pool.close()


# ── POST /documents/{id}/bind-to-deal/{deal_id} ──

@router.post("/{document_id}/bind-to-deal/{deal_id}")
async def bind_document_to_deal(document_id: str, deal_id: str):
    """Bind a recognized document to an existing deal.

    Resolves document_role → closes matching deal requirement.
    Idempotent: if already bound, returns existing.
    """
    import sys, json

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            intake = await conn.fetchrow(
                "SELECT id, classification, confidence, extracted_fields, status, company_id, file_name FROM accounting.document_intake WHERE id = $1",
                document_id
            )
            if not intake:
                raise HTTPException(status_code=404, detail="Document not found")

            existing_promoted = await conn.fetchval(
                "SELECT promoted_deal_id FROM accounting.document_intake WHERE id = $1", document_id
            )
            if existing_promoted == deal_id:
                return {"status": "already_bound", "deal_id": deal_id, "document_id": document_id}

            deal = await conn.fetchrow("SELECT id, title FROM public.deals WHERE id = $1 AND deleted_at IS NULL", deal_id)
            if not deal:
                raise HTTPException(status_code=404, detail="Deal not found")

            doc_type = intake["classification"] or "unknown"
            confidence = intake["confidence"] or 0.0
            file_name = intake["file_name"]

            import httpx
            raw_text = ""
            try:
                async with httpx.AsyncClient(timeout=5, proxy=None, trust_env=False) as client:
                    resp = await client.get(f"http://192.168.1.113:8000/api/v1/jobs/{document_id}")
                    if resp.status_code == 200:
                        nd = resp.json().get("normalized_document", {})
                        raw_text = nd.get("raw_text", "")
            except Exception:
                pass

            sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
            from domain.document_semantics.role_classifier import DocumentRoleClassifier
            classifier = DocumentRoleClassifier()
            doc_semantic = classifier.classify(doc_type, raw_text, confidence)
            role_key = doc_semantic.document_role.value

            ROLE_TO_REQ = {
                "transfer_act": "acceptance_act", "sale_contract": "dkp",
                "egrn_extract": "egrn_extract", "payment_order": "payment_order",
                "passport": "passport_seller", "invoice": "invoice",
                "receipt": "receipt", "certificate": "certificate",
                "cadastral": "cadastral_passport", "reconciliation": "reconciliation_act",
            }
            req_key = ROLE_TO_REQ.get(role_key, "")

            doc_id = str(uuid.uuid4())
            now = datetime.utcnow()
            system_user_id = "5055acf6-e7f2-4b9a-82f7-f19eba6caff6"
            await conn.execute(
                """INSERT INTO public.documents (id, document_type, status, title, file_name, file_path, file_size,
                    mime_type, uploaded_by, deal_id, created_at, updated_at)
                   VALUES ($1, $2, 'received', $3, $4, $5, $6, $7, $8, $9, $10, $10)""",
                doc_id, doc_type, file_name[:200], file_name, f"/intake/{document_id}", 0, "application/octet-stream",
                system_user_id, deal_id, now
            )

            pkg = None
            if req_key:
                pkg = await conn.fetchrow(
                    """SELECT dp.id, r.label FROM deal_document_packages dp
                       JOIN document_requirements r ON r.id = dp.requirement_id
                       WHERE dp.deal_id = $1 AND r.document_type = $2 AND dp.deleted_at IS NULL
                       LIMIT 1""", deal_id, req_key
                )

            requirement_matched = False
            if pkg:
                await conn.execute(
                    """UPDATE deal_document_packages
                       SET document_id=$1, requirement_status='verified', status='attached', verified=true,
                           document_role=$2, attached_at=$3, updated_at=$3
                       WHERE id=$4""",
                    doc_id, role_key, now, pkg["id"]
                )
                requirement_matched = True

            await conn.execute("UPDATE accounting.document_intake SET promoted_deal_id=$1 WHERE id=$2", deal_id, document_id)

            await conn.execute(
                """INSERT INTO deal_timeline_events (id, deal_id, event_type, source_component, title, description, metadata, created_at)
                   VALUES ($1, $2, 'document_received', 'document_pipeline', $3, $4, $5, $6)""",
                str(uuid.uuid4()), deal_id, f"Прикреплён: {file_name[:60]}",
                f"Роль: {role_key}, тип: {doc_type}",
                json.dumps({"doc_id": doc_id, "doc_role": role_key, "semantic_conf": doc_semantic.confidence}), now
            )

            return {
                "status": "bound", "deal_id": deal_id, "deal_title": deal["title"],
                "document_id": document_id, "document_role": role_key,
                "semantic_confidence": doc_semantic.confidence,
                "classification_source": doc_semantic.source.value,
                "requirement_matched": requirement_matched,
                "requirement_label": pkg["label"] if pkg else "",
            }
    finally:
        await pool.close()
