"""Clients API — direct asyncpg (bypasses SQLAlchemy session issues)."""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import asyncpg

router = APIRouter(tags=["clients"])

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros")
DSN = DSN.replace("+asyncpg", "")


class ClientResponse(BaseModel):
    id: str
    full_name: str
    phone: str | None
    email: str | None
    status: str | None
    source: str | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None


@router.get("", response_model=list[ClientResponse])
async def list_clients(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    conn = await asyncpg.connect(DSN)
    try:
        offset = (page - 1) * page_size
        rows = await conn.fetch(
            "SELECT id, full_name, phone, email, status, source, notes, "
            "created_by, created_at, updated_at FROM clients "
            "WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            page_size, offset
        )
        return [
            ClientResponse(
                id=str(r["id"]),
                full_name=r["full_name"],
                phone=r["phone"],
                email=r["email"],
                status=r["status"],
                source=r["source"],
                notes=r["notes"],
                created_by=str(r["created_by"]) if r["created_by"] else None,
                created_at=r["created_at"].isoformat() if r["created_at"] else None,
                updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
            )
            for r in rows
        ]
    finally:
        await conn.close()


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID):
    conn = await asyncpg.connect(DSN)
    try:
        r = await conn.fetchrow(
            "SELECT id, full_name, phone, email, status, source, notes, "
            "created_by, created_at, updated_at FROM clients "
            "WHERE id=$1 AND deleted_at IS NULL",
            str(client_id)
        )
        if not r:
            raise HTTPException(status_code=404, detail="Client not found")
        return ClientResponse(
            id=str(r["id"]),
            full_name=r["full_name"],
            phone=r["phone"],
            email=r["email"],
            status=r["status"],
            source=r["source"],
            notes=r["notes"],
            created_by=str(r["created_by"]) if r["created_by"] else None,
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
        )
    finally:
        await conn.close()
