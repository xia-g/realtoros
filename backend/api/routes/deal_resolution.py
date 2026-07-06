"""
Deal Resolution API — POST /api/v1/documents/{document_id}/resolve.

Read-only: возвращает ResolutionResult, не создаёт сделки.
Решение о promote/bind принимает клиент (UI или API caller).
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/documents", tags=["Deal Resolution"])


@router.post("/{document_id}/resolve")
async def resolve_document(document_id: str):
    """Resolve document to existing deal or new deal.

    Returns ResolutionResult with:
      - decision: auto_attach / review_required / create_new_deal
      - score: similarity score (0-110)
      - matched_deal_id: if found
      - candidates: list of candidate transactions
      - evidence: explainable matching evidence

    Read-only — does NOT create or modify deals.
    """
    import json
    import os
    import asyncpg

    DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
    DSN = DSN.replace("+asyncpg", "")

    pool = await asyncpg.create_pool(dsn=DSN, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            # 1. Load document intake
            intake = await conn.fetchrow(
                "SELECT id, classification, confidence, extracted_fields, file_name FROM accounting.document_intake WHERE id = $1",
                document_id
            )
            if not intake:
                raise HTTPException(status_code=404, detail="Document intake not found")

            doc_type = intake["classification"] or "unknown"
            file_name = intake["file_name"]

            # 2. Extract fields
            fields = {}
            if intake["extracted_fields"]:
                fields = json.loads(intake["extracted_fields"]) if isinstance(intake["extracted_fields"], str) else intake["extracted_fields"]

            # 3. Build DocumentFingerprint
            sys.path.insert(0, "/home/xiag/real-estate-os/services/accounting_binding")

            from domain.property.property_identity import PropertyIdentity
            from domain.deal_resolution.fingerprint import DocumentFingerprint
            from domain.deal_resolution.candidate_finder import CandidateFinder
            from domain.deal_resolution.similarity_scorer import SimilarityScorer
            from domain.deal_resolution.resolver import DealResolver

            # Try to get raw text from OCR Node
            import httpx
            raw_text = ""
            try:
                async with httpx.AsyncClient(timeout=5, proxy=None, trust_env=False) as client:
                    resp = await client.get(f"http://192.168.1.113:8000/api/v1/jobs/{document_id}")
                    if resp.status_code == 200:
                        nd = resp.json().get("normalized_document", {})
                        raw_text = nd.get("raw_text", "")
                        entities = nd.get("entities", {})
                        if entities and not fields:
                            fields = entities
            except Exception:
                pass

            # Extract entities for fingerprint
            amounts = []
            inns = []
            company_names = []
            person_names = []
            dates_found = []

            if isinstance(fields, dict):
                amounts = fields.get("amount", []) or fields.get("amounts", [])
                inns = fields.get("vat_number", []) or fields.get("inn", []) or fields.get("INN", [])
                company_names = fields.get("company", []) or fields.get("company_name", [])
                person_names = fields.get("persons", []) or fields.get("person", [])
                dates_found = fields.get("date", []) or fields.get("dates", [])

            # Parse amount
            amount = Decimal("0")
            if amounts:
                try:
                    amount = Decimal(str(max(float(a) for a in amounts if a)))
                except (ValueError, TypeError):
                    pass

            # Parse date
            contract_date = None
            if dates_found:
                try:
                    from datetime import datetime
                    for d in dates_found:
                        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                            try:
                                contract_date = datetime.strptime(d.strip(), fmt).date()
                                break
                            except (ValueError, IndexError):
                                continue
                        if contract_date:
                            break
                except Exception:
                    pass

            # Extract cadastral and address from text
            cadastral = PropertyIdentity.extract_cadastral(raw_text)
            address = fields.get("address", "") or fields.get("property_address", "") or ""

            # Extract counterparty
            counterparty_inn = inns[0] if inns else ""
            # party_identity was from OCR - use company/person names
            buyer = company_names[0] if company_names else person_names[0] if person_names else ""

            doc_fp = DocumentFingerprint(
                document_id=document_id,
                document_type=doc_type,
                document_role=fields.get("document_role", doc_type),
                raw_text=raw_text,
                entities=fields if isinstance(fields, dict) else {},
                amount=amount,
                contract_date=contract_date,
                contract_number=fields.get("document_number", [""])[0] if isinstance(fields.get("document_number"), list) else "",
                buyer=buyer,
                seller="",
                counterparty_inn=counterparty_inn,
                property_identity=PropertyIdentity(
                    cadastral_number=cadastral,
                    normalized_address=address,
                ),
            )

            # 4. Resolve
            class FakeDealStore:
                """Asyncpg-based deal store for candidate finding."""
                def __init__(self, conn):
                    self._conn = conn

                async def find_by_cadastral(self, cad: str) -> list[dict]:
                    if not cad:
                        return []
                    rows = await conn.fetch(
                        """SELECT id, deal_type, status, lifecycle_stage, title, price::text
                           FROM public.deals WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 20"""
                    )
                    return [dict(r) for r in rows]

                async def find_by_address(self, addr: str) -> list[dict]:
                    if not addr:
                        return []
                    rows = await conn.fetch(
                        "SELECT id, deal_type, status, lifecycle_stage, title, price::text FROM public.deals WHERE deleted_at IS NULL LIMIT 20"
                    )
                    return [dict(r) for r in rows]

                async def find_by_parties(self, buyer: str, seller: str, inn: str) -> list[dict]:
                    if not buyer and not seller:
                        return []
                    rows = await conn.fetch(
                        "SELECT id, deal_type, status, lifecycle_stage, title, price::text FROM public.deals WHERE deleted_at IS NULL LIMIT 20"
                    )
                    return [dict(r) for r in rows]

                async def find_by_contract(self, contract_number: str) -> list[dict]:
                    return []

                async def find_by_date_range(self, doc_date: date | None, days: int = 30) -> list[dict]:
                    return []

            finder = CandidateFinder(FakeDealStore(conn))
            resolver = DealResolver(finder)
            result = await resolver.resolve(doc_fp)

            return result.to_dict()
    finally:
        await pool.close()
