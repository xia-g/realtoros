"""Properties API — direct asyncpg (bypasses SQLAlchemy session issues)."""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
import asyncpg

router = APIRouter(tags=["properties"])

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
DSN = DSN.replace("+asyncpg", "")


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    property_type: str
    status: str
    deal_type: str
    title: str
    description: str | None
    address: str | None
    area_total: float | None
    area_living: float | None
    rooms: int | None
    floor: int | None
    floors_total: int | None
    price: float | None
    price_currency: str | None
    price_per_meter: float | None
    commission: float | None
    owner_id: str | None
    photos: list | None
    documents: list | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None


@router.get("", response_model=list[PropertyResponse])
async def list_properties(page: int = 1, page_size: int = 50):
    conn = await asyncpg.connect(DSN)
    try:
        offset = (page - 1) * page_size
        rows = await conn.fetch(
            "SELECT * FROM properties WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            page_size, offset
        )
        return [_prop(r) for r in rows]
    finally:
        await conn.close()


@router.get("/search", response_model=list[PropertyResponse])
async def search_properties(q: str = Query(..., min_length=1)):
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT * FROM properties WHERE deleted_at IS NULL AND "
            "(title ILIKE $1 OR address ILIKE $1 OR description ILIKE $1) LIMIT 20",
            f"%{q}%"
        )
        return [_prop(r) for r in rows]
    finally:
        await conn.close()


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: UUID):
    conn = await asyncpg.connect(DSN)
    try:
        r = await conn.fetchrow(
            "SELECT * FROM properties WHERE id=$1 AND deleted_at IS NULL",
            str(property_id)
        )
        if not r:
            raise HTTPException(status_code=404, detail="Property not found")
        return _prop(r)
    finally:
        await conn.close()


def _prop(r) -> PropertyResponse:
    return PropertyResponse(
        id=str(r["id"]),
        property_type=r["property_type"],
        status=r["status"],
        deal_type=r["deal_type"],
        title=r["title"],
        description=r.get("description"),
        address=r.get("address"),
        area_total=float(r["area_total"]) if r.get("area_total") else None,
        area_living=float(r["area_living"]) if r.get("area_living") else None,
        rooms=r.get("rooms"),
        floor=r.get("floor"),
        floors_total=r.get("floors_total"),
        price=float(r["price"]) if r.get("price") else None,
        price_currency=r.get("price_currency"),
        price_per_meter=float(r["price_per_meter"]) if r.get("price_per_meter") else None,
        commission=float(r["commission"]) if r.get("commission") else None,
        owner_id=str(r["owner_id"]) if r.get("owner_id") else None,
        photos=r.get("photos"),
        documents=r.get("documents"),
        notes=r.get("notes"),
        created_by=str(r["created_by"]) if r.get("created_by") else None,
        created_at=r["created_at"].isoformat() if r.get("created_at") else None,
        updated_at=r["updated_at"].isoformat() if r.get("updated_at") else None,
    )
