"""Deals API — direct asyncpg (bypasses SQLAlchemy session issues)."""

from __future__ import annotations

import os
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
import asyncpg

router = APIRouter(tags=["deals"])

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
DSN = DSN.replace("+asyncpg", "")


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    deal_type: str
    status: str
    property_id: str | None
    title: str
    description: str | None
    price: float | None
    price_currency: str | None
    commission: float | None
    commission_percent: float | None
    deposit_amount: float | None
    start_date: str | None
    end_date: str | None
    closing_date: str | None
    source: str | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None


@router.get("", response_model=list[DealResponse])
async def list_deals(page: int = 1, page_size: int = 50):
    conn = await asyncpg.connect(DSN)
    try:
        offset = (page - 1) * page_size
        rows = await conn.fetch(
            "SELECT * FROM deals WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            page_size, offset
        )
        return [_deal(r) for r in rows]
    finally:
        await conn.close()


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(deal_id: UUID):
    conn = await asyncpg.connect(DSN)
    try:
        r = await conn.fetchrow(
            "SELECT * FROM deals WHERE id=$1 AND deleted_at IS NULL",
            str(deal_id)
        )
        if not r:
            raise HTTPException(status_code=404, detail="Deal not found")
        return _deal(r)
    finally:
        await conn.close()


def _deal(r) -> DealResponse:
    return DealResponse(
        id=str(r["id"]),
        deal_type=r["deal_type"],
        status=r["status"],
        property_id=str(r["property_id"]) if r.get("property_id") else None,
        title=r["title"],
        description=r.get("description"),
        price=float(r["price"]) if r.get("price") else None,
        price_currency=r.get("price_currency"),
        commission=float(r["commission"]) if r.get("commission") else None,
        commission_percent=float(r["commission_percent"]) if r.get("commission_percent") else None,
        deposit_amount=float(r["deposit_amount"]) if r.get("deposit_amount") else None,
        start_date=r["start_date"].isoformat() if r.get("start_date") else None,
        end_date=r["end_date"].isoformat() if r.get("end_date") else None,
        closing_date=r["closing_date"].isoformat() if r.get("closing_date") else None,
        source=r.get("source"),
        notes=r.get("notes"),
        created_by=str(r["created_by"]) if r.get("created_by") else None,
        created_at=r["created_at"].isoformat() if r.get("created_at") else None,
        updated_at=r["updated_at"].isoformat() if r.get("updated_at") else None,
    )
