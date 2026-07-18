"""Document management API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.repositories import DocumentRepository

router = APIRouter()


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    docs, _ = await repo.list(page=1, page_size=100)
    return docs


@router.get("/{doc_id}")
async def get_document(doc_id: UUID, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    doc = await repo.get(doc_id)
    if doc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: UUID, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    success = await repo.delete(doc_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
