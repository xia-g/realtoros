"""Obligations & calendar — payment due dates, tax deadlines, compliance dates.

Schema: public.obligations
Tracks: payment type, amount, due date, status, linked document/event/company.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.accounting.db.pool import get_pool

router = APIRouter(prefix="/obligations", tags=["Obligations"])

OBLIGATION_TYPES = [
    "vat_payable",        # НДС к уплате
    "vat_deduction",      # НДС к вычету
    "tax_usn",            # УСН налог
    "tax_property",       # Налог на имущество
    "tax_land",           # Земельный налог
    "insurance",          # Страховые взносы
    "salary_tax",         # НДФЛ
    "loan_payment",       # Платеж по кредиту
    "rent",               # Аренда
    "utility",            # Коммунальные
    "counterparty",       # Контрагенту
    "other",              # Прочее
]


@router.on_event("startup")
async def ensure_table():
    """Create obligations table if not exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.obligations (
                id              UUID            NOT NULL DEFAULT gen_random_uuid(),
                company_id      UUID            NOT NULL,
                obligation_type VARCHAR(50)     NOT NULL,
                title           VARCHAR(300)    NOT NULL DEFAULT '',
                description     TEXT            NOT NULL DEFAULT '',
                amount          NUMERIC(16,2)   NOT NULL DEFAULT 0,
                due_date        DATE            NOT NULL,
                status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
                -- pending, paid, overdue, cancelled
                paid_amount     NUMERIC(16,2)   DEFAULT NULL,
                paid_date       DATE            DEFAULT NULL,
                document_id     UUID            DEFAULT NULL,
                event_id        UUID            DEFAULT NULL,
                linked_entity_type VARCHAR(50)  DEFAULT NULL,
                linked_entity_id   UUID         DEFAULT NULL,
                recurrence      VARCHAR(50)     DEFAULT NULL,
                -- monthly, quarterly, yearly, one_time
                reminder_days   INTEGER         NOT NULL DEFAULT 7,
                notes           TEXT            NOT NULL DEFAULT '',
                created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
                updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
                CONSTRAINT pk_obligations PRIMARY KEY (id),
                CONSTRAINT fk_obligations_company
                    FOREIGN KEY (company_id) REFERENCES public.companies(id)
                    ON DELETE CASCADE
            );
        """)


@router.get("")
async def list_obligations(
    company_id: str | None = None,
    status: str | None = None,
    obligation_type: str | None = None,
    limit: int = 50,
):
    """List obligations with optional filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params: list[Any] = []
        idx = 1

        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if obligation_type:
            where.append(f"obligation_type = ${idx}")
            params.append(obligation_type)
            idx += 1

        query = f"""
            SELECT o.*, c.name as company_name
            FROM public.obligations o
            JOIN public.companies c ON c.id = o.company_id
            WHERE {' AND '.join(where)}
            ORDER BY o.due_date ASC, o.created_at DESC
            LIMIT ${idx}
        """
        params.append(limit)

        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


@router.post("")
async def create_obligation(body: dict):
    """Create a new obligation."""
    required = ["company_id", "obligation_type", "title", "amount", "due_date"]
    for field in required:
        if field not in body:
            raise HTTPException(400, f"Missing required field: {field}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO public.obligations
               (company_id, obligation_type, title, description, amount, due_date,
                linked_entity_type, linked_entity_id, recurrence, reminder_days, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
               RETURNING *""",
            body["company_id"],
            body["obligation_type"],
            body["title"],
            body.get("description", ""),
            body["amount"],
            body["due_date"],
            body.get("linked_entity_type"),
            body.get("linked_entity_id"),
            body.get("recurrence", "one_time"),
            body.get("reminder_days", 7),
            body.get("notes", ""),
        )
        return dict(row)


@router.patch("/{obligation_id}")
async def update_obligation(obligation_id: str, body: dict):
    """Update obligation status, amount, dates."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build SET clause from provided fields
        setters: list[str] = []
        params: list[Any] = []
        idx = 1

        for field in ("status", "paid_amount", "paid_date", "title", "description",
                       "amount", "due_date", "notes", "reminder_days"):
            if field in body:
                setters.append(f"{field} = ${idx}")
                params.append(body[field])
                idx += 1

        if not setters:
            raise HTTPException(400, "No fields to update")

        setters.append("updated_at = now()")
        params.append(obligation_id)

        row = await conn.fetchrow(
            f"UPDATE public.obligations SET {', '.join(setters)} WHERE id = ${idx} RETURNING *",
            *params,
        )
        if not row:
            raise HTTPException(404, "Obligation not found")
        return dict(row)


@router.get("/overdue")
async def overdue_obligations(days: int = 30):
    """Get upcoming and overdue obligations."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.*, c.name as company_name,
                      CASE
                          WHEN o.due_date < CURRENT_DATE AND o.status = 'pending' THEN 'overdue'
                          WHEN o.due_date <= CURRENT_DATE + $1::integer AND o.status = 'pending' THEN 'upcoming'
                          ELSE o.status
                      END as calendar_status
               FROM public.obligations o
               JOIN public.companies c ON c.id = o.company_id
               WHERE o.status IN ('pending', 'overdue')
                 AND o.due_date <= CURRENT_DATE + $1::integer
               ORDER BY o.due_date ASC
            """,
            days,
        )
        return [dict(r) for r in rows]


@router.delete("/{obligation_id}", status_code=204)
async def delete_obligation(obligation_id: str):
    """Delete an obligation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM public.obligations WHERE id = $1", obligation_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Obligation not found")


@router.get("/types")
async def obligation_types():
    """List available obligation types."""
    return OBLIGATION_TYPES
