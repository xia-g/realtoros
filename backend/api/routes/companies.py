"""Company settings API — manage organization metadata.

Public schema — NOT accounting schema, no freeze violation.
Fields: name, INN, KPP, OGRN, addresses, bank details, CEO.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.accounting.db.pool import get_pool

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("")
async def list_companies():
    """List all companies with their settings."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ensure table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.companies (
                id              UUID            NOT NULL DEFAULT gen_random_uuid(),
                name            VARCHAR(200)    NOT NULL DEFAULT '',
                inn             VARCHAR(12)     NOT NULL DEFAULT '',
                kpp             VARCHAR(9)      NOT NULL DEFAULT '',
                ogrn            VARCHAR(15)     NOT NULL DEFAULT '',
                legal_address   TEXT            NOT NULL DEFAULT '',
                actual_address  TEXT            NOT NULL DEFAULT '',
                okved           VARCHAR(20)     NOT NULL DEFAULT '',
                bank_name       VARCHAR(200)    NOT NULL DEFAULT '',
                bank_bik        VARCHAR(9)      NOT NULL DEFAULT '',
                bank_account    VARCHAR(20)     NOT NULL DEFAULT '',
                phone           VARCHAR(20)     NOT NULL DEFAULT '',
                email           VARCHAR(100)    NOT NULL DEFAULT '',
                ceo_name        VARCHAR(200)    NOT NULL DEFAULT '',
                ceo_position    VARCHAR(200)    NOT NULL DEFAULT '',
                tax_regime      VARCHAR(100)    NOT NULL DEFAULT 'usn_income',
                is_active       BOOLEAN         NOT NULL DEFAULT true,
                created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
                CONSTRAINT pk_companies PRIMARY KEY (id)
            );
        """)
        rows = await conn.fetch("SELECT * FROM public.companies ORDER BY name")
        return {"companies": [dict(r) for r in rows]}


@router.get("/{company_id}")
async def get_company(company_id: str):
    """Get a single company with all settings."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM public.companies WHERE id = $1", company_id)
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")
        # Also load tax_regime info
        regime = await conn.fetchrow(
            "SELECT regime_type, valid_from, valid_to FROM accounting.tax_regime WHERE company_id = $1 AND is_active = true",
            company_id,
        )
        result = dict(row)
        if regime:
            result["regime_type"] = regime["regime_type"]
            result["regime_valid_from"] = str(regime["valid_from"]) if regime["valid_from"] else None
            result["regime_valid_to"] = str(regime["valid_to"]) if regime["valid_to"] else None
        return result


@router.post("")
async def create_company(body: dict[str, Any]):
    """Create a new company."""
    pool = await get_pool()
    cid = str(body.get("id", uuid.uuid4()))
    async with pool.acquire() as conn:
        # Build combined regime: main + extra
        main_regime = body.get("tax_regime", "usn_income")
        extra_regime = body.get("tax_regime_extra", "")
        combined = f"{main_regime}+{extra_regime}" if extra_regime else main_regime

        await conn.execute(
            """INSERT INTO public.companies
               (id, name, inn, kpp, ogrn, legal_address, actual_address,
                okved, bank_name, bank_bik, bank_account,
                phone, email, ceo_name, ceo_position, tax_regime)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
            cid,
            body.get("name", ""),
            body.get("inn", ""),
            body.get("kpp", ""),
            body.get("ogrn", ""),
            body.get("legal_address", ""),
            body.get("actual_address", ""),
            body.get("okved", ""),
            body.get("bank_name", ""),
            body.get("bank_bik", ""),
            body.get("bank_account", ""),
            body.get("phone", ""),
            body.get("email", ""),
            body.get("ceo_name", ""),
            body.get("ceo_position", ""),
            combined,
        )
        # Also create tax_regime entry if not exists (store main regime)
        existing = await conn.fetchval(
            "SELECT id FROM accounting.tax_regime WHERE company_id = $1", cid,
        )
        if not existing:
            await conn.execute(
                "INSERT INTO accounting.tax_regime (id, company_id, regime_type, valid_from, settings_json, is_active) "
                "VALUES ($1, $2, $3, '2026-01-01', '{}'::jsonb, true)",
                uuid.uuid4(), cid, main_regime,
            )
    return {"id": cid, "status": "created"}


@router.put("/{company_id}")
async def update_company(company_id: str, body: dict[str, Any]):
    """Update company settings."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT id FROM public.companies WHERE id = $1", company_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Company not found")

        fields = []
        params = []
        idx = 1
        for key in ("name", "inn", "kpp", "ogrn", "legal_address", "actual_address",
                     "okved", "bank_name", "bank_bik", "bank_account",
                     "phone", "email", "ceo_name", "ceo_position", "tax_regime"):
            if key in body:
                fields.append(f"{key} = ${idx}")
                params.append(body[key])
                idx += 1

        if fields:
            fields.append("updated_at = now()")
            params.append(company_id)
            await conn.execute(
                f"UPDATE public.companies SET {', '.join(fields)} WHERE id = ${idx}",
                *params,
            )

        # Build combined regime for tax_regime update
        main_regime = body.get("tax_regime") or body.get("tax_regime", "")
        extra_regime = body.get("tax_regime_extra", "")
        combined = f"{main_regime}+{extra_regime}" if extra_regime else main_regime

        # Update tax_regime field with combined value
        if combined:
            await conn.execute(
                "UPDATE public.companies SET tax_regime = $2, updated_at = now() WHERE id = $1",
                company_id, combined,
            )

        # Update tax_regime in accounting schema (store main regime only)
        if "tax_regime" in body or "tax_regime_extra" in body:
            await conn.execute(
                "UPDATE accounting.tax_regime SET regime_type = $2 WHERE company_id = $1 AND is_active = true",
                company_id, main_regime or body.get("tax_regime", "usn_income"),
            )

    return {"id": company_id, "status": "updated"}
