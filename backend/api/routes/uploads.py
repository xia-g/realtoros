"""
Upload endpoints — document intake via OCR Node + Party Identity.

Pipeline: upload → OCR Node (GPU) → party identity → classify → store
Fallback: if OCR Node unavailable → local tesseract OCR

Результат:
- document_id, classification, confidence
- extracted_fields (amounts, dates, INN)
- parties (party identity resolution)
- transaction_tags
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, Request

from backend.accounting.db.pool import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Uploads"])

# OCR Node settings
OCR_NODE_URL = os.environ.get(
    "OCR_NODE_URL",
    "http://192.168.1.113:8000/api/v1",
)
OCR_FALLBACK = os.environ.get("OCR_NODE_FALLBACK", "false").lower() == "true"
OCR_POLL_INTERVAL = 3
OCR_MAX_RETRIES = 120  # 6 мин (первый запуск — загрузка PaddleOCR в GPU)


async def _ocr_node_submit(file_content: bytes, filename: str) -> str | None:
    """Отправить файл на OCR Node, вернуть job_id."""
    import httpx
    async with httpx.AsyncClient(timeout=5, proxy=None, trust_env=False) as client:
        files = {"file": (filename, file_content)}
        try:
            resp = await client.post(f"{OCR_NODE_URL}/jobs", files=files)
            if resp.status_code == 202:
                data = resp.json()
                return data.get("job_id")
            logger.warning("OCR Node submit failed: %d %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("OCR Node unreachable (Windows GPU): %s", e)
    return None


async def _ocr_node_poll(job_id: str) -> dict[str, Any] | None:
    """Опрашивать OCR Node до completion (максимум 10 сек)."""
    import httpx
    async with httpx.AsyncClient(timeout=10, proxy=None, trust_env=False) as client:
        for _ in range(OCR_MAX_RETRIES):
            await asyncio.sleep(OCR_POLL_INTERVAL)
            try:
                resp = await client.get(f"{OCR_NODE_URL}/jobs/{job_id}")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                status = data.get("status", "")
                if status in ("completed", "need_review"):
                    nd = data.get("normalized_document", {})
                    return {
                        "job_id": data.get("job_id", ""),
                        "classification": nd.get("document_type", "unknown"),
                        "confidence": nd.get("confidence", {}).get("overall_confidence", 0.0),
                        "entities": nd.get("entities", {}),
                        "raw_text": nd.get("raw_text", ""),
                        "status": status,
                    }
                if status == "failed":
                    logger.error("OCR Node failed: %s", data.get("error", ""))
                    return None
            except Exception as e:
                logger.warning("OCR Node poll error: %s", e)
    logger.warning("OCR Node poll timeout for job %s", job_id)
    return None


async def _party_classify(
    company_names: list[str],
    person_names: list[str],
    counterparty_inn: str = "",
) -> dict[str, Any]:
    """Запустить Party Identity Resolution."""
    try:
        import sys
        sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
        from domain.enrichment.party_classifier import PartyClassifier
        from domain.enrichment.party_identity import MasterDataStore, PartyIdentity, EntityType, BusinessStatus

        class DbMasterData(MasterDataStore):
            async def find_by_inn(self, inn: str) -> list[PartyIdentity]:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT id, name, inn, kpp FROM public.companies WHERE inn = $1", inn
                    )
                    if row:
                        return [PartyIdentity(
                            party_id=str(row["id"]), name=row["name"], inn=row["inn"],
                            entity_type=EntityType.LEGAL_ENTITY, business_status=BusinessStatus.COMPANY,
                            confidence=1.0,
                        )]
                return []

            async def find_by_name(self, name: str) -> list[PartyIdentity]:
                return []

            async def get_our_companies(self) -> list[PartyIdentity]:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch("SELECT id, name, inn, kpp FROM public.companies")
                    return [
                        PartyIdentity(
                            party_id=str(r["id"]), name=r["name"], inn=r["inn"],
                            entity_type=EntityType.LEGAL_ENTITY, business_status=BusinessStatus.COMPANY,
                            confidence=1.0,
                        ) for r in rows
                    ]

        classifier = PartyClassifier(master_data=DbMasterData())
        result = await classifier.classify(
            company_names=company_names,
            person_names=person_names,
            counterparty_inn=counterparty_inn,
        )
        return {
            "parties": [
                {
                    "identity": {
                        "name": p.identity.name,
                        "entity_type": p.identity.entity_type.value,
                        "business_status": p.identity.business_status.value,
                        "confidence": p.identity.confidence,
                        "source": p.identity.source.value if hasattr(p.identity.source, "value") else str(p.identity.source),
                    },
                    "relation": {
                        "role": p.relation.role.value,
                        "relation": p.relation.relation.value,
                        "confidence": p.relation.confidence,
                    },
                }
                for p in result.parties
            ],
            "transaction_tags": result.tags,
            "classification_hash": result.classification_hash,
            "party_warnings": result.warnings,
        }
    except Exception as e:
        logger.warning("Party classifier failed: %s", e)
        return {"parties": [], "transaction_tags": [], "classification_hash": "", "party_warnings": [str(e)]}


@router.post("/document")
async def upload_document(
    file: UploadFile,
    company_id: str | None = None,
):
    """Upload → OCR Node (GPU) → возвращает job_id для опроса.

    Асинхронно: ответ сразу, результат — через GET /upload/job/{job_id}.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    logger.info("Upload: file=%s size=%d", file.filename, len(content))
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Resolve company
    if not company_id:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM public.companies WHERE is_active = true ORDER BY name LIMIT 1"
            )
            if not row:
                raise HTTPException(status_code=400, detail="No active companies found")
            company_id = str(row["id"])

    # Submit to OCR Node
    logger.info("OCR Node: submitting file...")
    job_id = await _ocr_node_submit(content, file.filename)
    if not job_id:
        raise HTTPException(
            status_code=503,
            detail="OCR Node (GPU-распознавание на Windows) недоступен. "
                   "Убедитесь, что машина 192.168.1.113 включена, "
                   "или используйте локальный Tesseract (медленнее, без GPU)."
        )

    # Save file reference to DB for later polling
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO accounting.document_intake
               (id, company_id, file_name, file_size, mime_type, status, classification, file_hash)
               VALUES ($1, $2, $3, $4, $5, 'pending', 'unknown', $6)
               ON CONFLICT (id) DO UPDATE
               SET status='pending', file_size=$4""",
            job_id, company_id, file.filename, len(content), file.content_type or "application/octet-stream",
            hashlib.sha256(content).hexdigest(),
        )

    logger.info("Upload accepted: job=%s company=%s", job_id[:8], company_id[:8])
    return {
        "job_id": job_id,
        "status": "pending",
        "filename": file.filename,
        "file_size": len(content),
        "message": "Документ отправлен на распознавание. Результат будет доступен через GET /api/v1/upload/job/{job_id}",
    }


@router.get("/job/{job_id}")
async def get_upload_job(job_id: str, request: Request = None):
    """Проверить статус OCR и получить результат.

    Неблокирующий: быстрый check, без ожидания.
    Если OCR не готов — pending, если готов — полный результат.
    """
    # Быстрый non-blocking check OCR Node
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5, proxy=None, trust_env=False) as client:
            resp = await client.get(f"{OCR_NODE_URL}/jobs/{job_id}")
            if resp.status_code != 200:
                return {"job_id": job_id, "status": "unknown", "error": f"OCR Node returned {resp.status_code}"}
            data = resp.json()
            status = data.get("status", "")

            # If still processing — return pending immediately
            if status not in ("completed", "need_review", "failed"):
                return {"job_id": job_id, "status": "pending"}

            # If failed — return error
            if status == "failed":
                return {"job_id": job_id, "status": "failed", "error": data.get("error", "OCR failed")}

            # OCR done — parse result
            nd = data.get("normalized_document", {})
            ocr_status = status
            ocr_result = {
                "classification": nd.get("document_type", "unknown"),
                "confidence": nd.get("confidence", {}).get("overall_confidence", 0.0),
                "entities": nd.get("entities", {}),
                "raw_text": nd.get("raw_text", ""),
                "status": status,
            }

            logger.info("OCR completed: job=%s status=%s", job_id[:8], status)

            # Semantic reclassification
            raw_text = ocr_result.get("raw_text", "")
            ocr_type = ocr_result.get("classification", "unknown")
            ocr_conf = ocr_result.get("confidence", 0.0)
            final_type = ocr_type
            final_confidence = ocr_conf
            semantic_type = ""
            semantic_conf = 0.0
            semantic_signals = []
            document_role = "unknown"

            try:
                sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
                from domain.enrichment.semantic_classifier import SemanticReclassifier
                reclassifier = SemanticReclassifier()
                semantic = reclassifier.classify(raw_text=raw_text, ocr_type=ocr_type, ocr_confidence=ocr_conf)
                final_type = semantic.final_type
                final_confidence = semantic.final_confidence
                semantic_type = semantic.semantic_type
                semantic_conf = semantic.semantic_confidence
                semantic_signals = semantic.signals
                logger.info("Semantic reclass: OCR '%s' → final '%s' (%.2f)", ocr_type, final_type, final_confidence)
            except Exception as e:
                logger.warning("Semantic classifier failed: %s", e)

            # Document Role Resolution
            try:
                sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
                from domain.document_semantics.role_classifier import DocumentRoleClassifier
                role_cls = DocumentRoleClassifier()
                doc_semantic = role_cls.classify(final_type, raw_text, final_confidence)
                document_role = doc_semantic.document_role.value
                logger.info("Document role: %s → %s (conf=%.2f)", final_type, document_role, doc_semantic.confidence)
            except Exception as e:
                logger.warning("Document role classifier failed: %s", e)

            # Party Identity
            company_names = ocr_result.get("entities", {}).get("company", [])
            person_names = ocr_result.get("entities", {}).get("persons", [])
            vat = ocr_result.get("entities", {}).get("vat_number", [])
            counterparty_inn = vat[0] if vat else ""

            party_result = await _party_classify(
                company_names=company_names or [],
                person_names=person_names,
                counterparty_inn=counterparty_inn,
            )

            # Deal Resolution — match to existing deals
            resolution = None
            try:
                sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
                from domain.deal_resolution.resolver import DealResolver
                from domain.deal_resolution.candidate_finder import CandidateFinder
                from domain.deal_resolution.fingerprint import DocumentFingerprint
                from domain.property.property_identity import PropertyIdentity
                from decimal import Decimal as _Dec
                from datetime import date as _Date

                amounts = ocr_result.get("entities", {}).get("amount", [])
                amount_val = _Dec("0")
                if amounts:
                    try: amount_val = _Dec(str(max(float(a) for a in amounts)))
                    except: pass

                cadastral = PropertyIdentity.extract_cadastral(raw_text)
                buyer = company_names[0] if company_names else person_names[0] if person_names else ""

                # Extract contract number and date from raw_text
                contract_no = ""
                contract_dt = None
                import re as _re
                for line in raw_text.split("\n"):
                    line_s = line.strip()
                    # № 2182-НШИИ or No 2182-Н or номер 2182
                    m = _re.search(r"[№#НNn]\s*([\w\-]+)", line_s)
                    if m:
                        contract_no = m.group(1)
                    m = _re.search(r"(\d{2})[./](\d{2})[./](\d{4})", line_s)
                    if m:
                        try: contract_dt = _Date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                        except: pass
                    if contract_no and contract_dt:
                        break

                doc_fp = DocumentFingerprint(
                    document_id=job_id, document_type=final_type, document_role=document_role,
                    raw_text=raw_text, amount=amount_val, buyer=buyer,
                    contract_number=contract_no, contract_date=contract_dt,
                    counterparty_inn=counterparty_inn,
                    property_identity=PropertyIdentity(cadastral_number=cadastral) if cadastral else None,
                )

                db_pool = await get_pool()
                async with db_pool.acquire() as db_conn:
                    class LiveStore:
                        def __init__(self, c): self._c = c
                        async def find_by_cadastral(self, cad):
                            if not cad: return []
                            return [dict(r) for r in await self._c.fetch("SELECT d.id, d.deal_type, d.status, d.lifecycle_stage, d.title, d.price::text, dp.document_role, dp.requirement_status FROM public.deals d LEFT JOIN deal_document_packages dp ON dp.deal_id = d.id WHERE d.deleted_at IS NULL AND dp.requirement_status = 'verified' AND dp.document_role = 'sale_contract' LIMIT 20")]
                        async def find_by_address(self, addr):
                            if not addr: return []
                            return [dict(r) for r in await self._c.fetch("SELECT id, deal_type, status, lifecycle_stage, title, price::text FROM public.deals WHERE deleted_at IS NULL LIMIT 20")]
                        async def find_by_parties(self, b, s, inn):
                            if not inn and not b and not s: return []
                            return [dict(r) for r in await self._c.fetch(
                                "SELECT d.id, d.deal_type, d.status, d.lifecycle_stage, d.title, d.price::text FROM public.deals d WHERE d.deleted_at IS NULL LIMIT 20")]
                        async def find_by_contract(self, cn):
                            if not cn: return []
                            return [dict(r) for r in await self._c.fetch("SELECT id, deal_type, status, lifecycle_stage, title, price::text FROM public.deals WHERE deleted_at IS NULL AND title ILIKE $1 LIMIT 5", f"%{cn}%")]
                        async def find_by_date_range(self, dd, days=30):
                            return []

                    finder = CandidateFinder(LiveStore(db_conn))
                    resolver = DealResolver(finder)
                    resolution = await resolver.resolve(doc_fp)
            except Exception as e:
                logger.warning("Deal resolution failed: %s", e)

            # v2.0.1 — Business Entity & Fact Extraction (log only, no DB)
            try:
                sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
                from domain.business_relationship.entity_extractor import EntityExtractor
                from domain.business_relationship.entity_resolver import EntityResolver
                from domain.business_relationship.fact_extractor import FactExtractor
                from domain.business_relationship.extraction_context import ExtractionContext

                amounts_val = ocr_result.get("entities", {}).get("amount", [])

                extractor = EntityExtractor()
                raw_entities, raw_identifiers = extractor.extract(
                    ocr_entities=ocr_result.get("entities", {}),
                    raw_text=raw_text,
                    document_id=job_id,
                    semantic_type=final_type,
                    company_names=company_names,
                    person_names=person_names,
                    vat_numbers=vat,
                )

                resolver = EntityResolver()
                resolved_entities = []
                resolved_identifiers = []
                unmatched_entities = list(raw_entities)
                # Resolve each extracted entity
                while unmatched_entities:
                    e = unmatched_entities.pop(0)
                    entity_idfs = [idf for idf in raw_identifiers if idf.entity_id == e.id]
                    matched_entity, _ = resolver.resolve(entity_idfs, entity_type=e.entity_type, display_name=e.display_name)
                    resolved_entities.append(matched_entity)
                    resolved_identifiers.extend([idf for idf in entity_idfs])

                fact_extractor = FactExtractor()
                facts = fact_extractor.extract(
                    entities=resolved_entities,
                    identifiers=resolved_identifiers,
                    document_id=job_id,
                    document_role=document_role,
                    semantic_type=final_type,
                    ocr_entities=ocr_result.get("entities", {}),
                    amounts=amounts_val,
                    raw_text=raw_text,
                )

                ctx = ExtractionContext(
                    document_id=job_id,
                    entities=resolved_entities,
                    identifiers=resolved_identifiers,
                    facts=facts,
                )

                # v2.0.1a — Document Reference Extraction
                from domain.business_relationship.document_reference import DocumentReference, ReferenceType
                from domain.business_relationship.provenance import Provenance, DocumentRevision
                import re as _re2
                doc_refs = []
                if raw_text:
                    contract_match = _re2.search(r"[№#НNn]\s*(?P<num>[\w\-\.\/]+)", raw_text)
                    ref_num = contract_match.group("num") if contract_match else ""
                    # Detect reference type from text
                    if "акт" in raw_text.lower() and "договор" in raw_text.lower():
                        doc_refs.append(DocumentReference(
                            reference_type=ReferenceType.ACT_FOR,
                            source_document_id=job_id,
                            target_document_identifier=ref_num,
                            provenance=Provenance(document_revision=DocumentRevision(document_id=job_id)),
                            confidence=0.80,
                        ))
                    elif "приложение" in raw_text.lower():
                        doc_refs.append(DocumentReference(
                            reference_type=ReferenceType.APPENDIX_TO,
                            source_document_id=job_id,
                            target_document_identifier=ref_num,
                            provenance=Provenance(document_revision=DocumentRevision(document_id=job_id)),
                            confidence=0.75,
                        ))
                    elif ref_num:
                        doc_refs.append(DocumentReference(
                            reference_type=ReferenceType.REFERS_TO,
                            source_document_id=job_id,
                            target_document_identifier=ref_num,
                            provenance=Provenance(document_revision=DocumentRevision(document_id=job_id)),
                            confidence=0.70,
                        ))
                ctx.document_references = doc_refs

                logger.info("v2.0.1a ExtractionContext: %s", ctx.summary)
                for f in facts[:10]:
                    logger.debug("  Fact: %s (conf=%.2f)", f, f.confidence)
                for ref in doc_refs:
                    logger.debug("  Ref: %s → %s (%s)", ref.source_document_id[:12], ref.target_document_identifier, ref.reference_type.value)

                # v2.0.2 — Agreement Resolution
                from domain.business_relationship.agreement_resolver import AgreementResolver
                from domain.business_relationship.semantic_interpreter import SemanticInterpreter
                from domain.business_relationship.agreement_matcher import AgreementMatcher

                # Use existing agreement matcher (session-level if available, otherwise new)
                matcher = AgreementMatcher()
                resolver = AgreementResolver(matcher=matcher)
                ag_ctx = resolver.resolve(
                    document_role=document_role,
                    semantic_type=final_type,
                    facts=facts,
                    entities=resolved_entities,
                    document_id=job_id,
                    document_references=doc_refs,
                    raw_text=raw_text,
                )
                logger.info("v2.0.2 AgreementContext: %s", ag_ctx.summary)
                for ev in ag_ctx.resolution_evidence:
                    logger.debug("  Evidence: %s", ev)

                # v2.0.3 — Identity Resolution
                from domain.business_relationship.identity_resolver import IdentityResolver
                identity = IdentityResolver()
                master_ctx = identity.resolve(
                    entities=resolved_entities,
                    identifiers=resolved_identifiers,
                    agreement=ag_ctx.agreement,
                    facts=facts,
                    document_id=job_id,
                )
                logger.info("v2.0.3 MasterDataContext: %s", master_ctx.summary)
                for ev in master_ctx.resolution_evidence[:10]:
                    logger.debug("  Master: %s", ev)
                if master_ctx.merge_candidates:
                    for mc in master_ctx.merge_candidates:
                        logger.info("  Merge candidate: %s ↔ %s (score=%.1f, %s)",
                                     mc.left_entity_id[:8], mc.right_entity_id[:8],
                                     mc.similarity_score, mc.decision.value)

                # v2.0.4 — Knowledge Evolution
                from domain.business_relationship.knowledge_evolution import KnowledgeEvolutionService
                from domain.business_relationship.trust import TrustLevel
                evolution = KnowledgeEvolutionService()
                for ce in master_ctx.canonical_entities:
                    evolution.on_entity_created(ce.id, job_id, ce.display_name)
                    for alias in ce.aliases:
                        evolution.on_alias_added(ce.id, alias.original_value, alias.normalized_value, job_id)
                    if ce.confidence > 0:
                        evolution.on_confidence_updated(ce.id, 0.0, ce.confidence, job_id)
                    ts = evolution.get_trust(ce.id)
                    if ts:
                        evolution.on_trust_updated(ce.id, TrustLevel.UNKNOWN.value, ts.current_level.value, job_id)
                for cp in master_ctx.canonical_properties:
                    evolution.on_entity_created(cp.id, job_id, cp.cadastral_number)
                for ca in master_ctx.canonical_agreements:
                    evolution.on_entity_created(ca.id, job_id, ca.number)
                evo_result = evolution.result()
                logger.info("v2.0.4 KnowledgeEvolution: events=%d, conflicts=%d, entities_with_trust=%d",
                             len(evo_result.events), len(evo_result.conflicts),
                             len(evo_result.trust_scores))

                # v2.0.5 — Knowledge Graph
                from domain.business_relationship.knowledge_graph import GraphBuilder
                builder = GraphBuilder()
                graph = builder.build(
                    document_id=job_id,
                    entities=resolved_entities,
                    properties=[],  # no extra property references yet
                    agreement_id=ag_ctx.agreement.id if ag_ctx.agreement else "",
                    document_references=doc_refs,
                )
                logger.info("v2.0.5 Graph: %s", graph.summary())

            except Exception as e:
                logger.warning("v2.0.1 extraction failed: %s", e)

            # ── v2.1 Domain Pipeline ─────────────────────────────
            try:
                sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")
                from application.domain_pipeline_bridge import DomainPipelineBridge
                bridge = DomainPipelineBridge()
                pipeline_result = bridge.process(
                    document_id=job_id,
                    raw_text=raw_text or "",
                    entities=ocr_result.get("entities", {}),
                    classification=final_type,
                    confidence=final_confidence,
                    semantic_type=semantic_type,
                    document_role=document_role,
                )
                logger.info(
                    "v2.1 Pipeline: revision=%s graph=%d nodes provenance=%d links",
                    pipeline_result["revision"]["id"][:8],
                    pipeline_result["graph"]["node_count"],
                    pipeline_result["provenance_links"],
                )

            # ── v2.1.5 Runtime Integration ─────────────────────
                try:
                    from application.knowledge_persistence.integrator import (
                        KnowledgeRuntimeIntegrator,
                    )
                    # Get integrator from app.state (bootstrapped in lifespan)
                    _integrator = request.app.state.integrator

                    report = _integrator.integrate(
                        pipeline_result=pipeline_result,
                        source_document_id=job_id,
                        processing_job_id=job_id,
                    )
                    if report.status == "completed":
                        logger.info(
                            "v2.1.5: revision=%s projections=%d queries=%d status=%s",
                            report.revision_id[:12] if report.revision_id else "?",
                            report.projection_count,
                            len(report.query_result_counts),
                            report.status,
                        )
                    else:
                        logger.warning(
                            "v2.1.5: revision=%s status=%s errors=%d",
                            report.revision_id[:12] if report.revision_id else "?",
                            report.status, report.error_count,
                        )
                except Exception as e2e:
                    logger.warning("v2.1.5 integration failed: %s", e2e)
                    e2e_result = {"error": str(e2e), "status": "exception"}
            except Exception as e:
                logger.warning("v2.1 Domain Pipeline failed: %s", e)
                pipeline_result = None

            # Update DB record
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO accounting.document_intake
                       (id, company_id, file_name, file_hash, file_size, classification, confidence, status,
                        extracted_fields, final_type, created_at)
                       VALUES ($1, '00000000-0000-0000-0000-000000000000', '', $2, 0, $3, $4, 'completed', $5::jsonb, $6, NOW())
                       ON CONFLICT (id) DO UPDATE
                       SET classification=$3, confidence=$4, status='completed',
                           extracted_fields=$5::jsonb, final_type=$6""",
                    job_id, hashlib.sha256(b"").hexdigest(),
                    final_type, round(final_confidence, 2),
                    json.dumps(ocr_result.get("entities", {})),
                    ocr_type,
                )

            return {
                "job_id": job_id,
                "status": "completed",
                "ocr_status": status,
                "review_state": "not_required" if status == "completed" else "required",
                "review_required": status == "need_review",
                "classification": final_type,
                "confidence": round(final_confidence, 2),
                "ocr_type": ocr_type,
                "ocr_confidence": round(ocr_conf, 2),
                "semantic_type": semantic_type,
                "semantic_confidence": round(semantic_conf, 2),
                "semantic_signals": semantic_signals,
                "document_role": document_role,
                "resolution": resolution.to_dict() if resolution else None,
                "extracted_text_preview": raw_text[:300],
                "extracted_fields": {
                    "amounts": ocr_result.get("entities", {}).get("amount", []),
                    "dates": ocr_result.get("entities", {}).get("date", []),
                    "inn": counterparty_inn,
                    "counterparty": company_names[0] if company_names else "",
                },
                "parties": party_result.get("parties", []),
                "transaction_tags": party_result.get("transaction_tags", []),
                "party_warnings": party_result.get("party_warnings", []),
                "v2_1_pipeline": pipeline_result,
            }
    except httpx.ConnectError:
        return {"job_id": job_id, "status": "error", "error": "OCR Node недоступен"}
    except Exception as e:
        logger.error("get_upload_job error: %s", e)
        return {"job_id": job_id, "status": "error", "error": str(e)}
