"""Knowledge Session API — conversational memory management.

All endpoints enforce ownership: users see only their own sessions.
SECURITY: session_id from path is always validated against current_user.id.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session, get_current_user
from backend.services.knowledge.memory.memory_service import MemoryService

router = APIRouter()


def _require_user(user_id: str | None) -> str:
    """Ensure authenticated user exists."""
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid token or user context.",
        )
    return user_id


@router.get("")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_expired: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_current_user),
):
    uid = _require_user(user_id)
    svc = MemoryService(session)
    sessions, total = await svc.list_sessions(
        user_id=UUID(uid),
        page=page,
        page_size=page_size,
        include_expired=include_expired,
    )
    return {
        "items": [
            {
                "id": str(s.id),
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "last_activity_at": s.last_activity_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "is_active": s.is_active,
                "message_count": s.message_count,
            }
            for s in sessions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_session(
    title: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_current_user),
):
    uid = _require_user(user_id)
    svc = MemoryService(session)
    summary = await svc.create_session(
        user_id=UUID(uid),
        title=title,
    )
    await session.commit()
    return {
        "id": str(summary.id),
        "title": summary.title,
        "created_at": summary.created_at.isoformat(),
        "last_activity_at": summary.last_activity_at.isoformat(),
        "expires_at": summary.expires_at.isoformat(),
        "is_active": summary.is_active,
        "message_count": summary.message_count,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_current_user),
):
    uid = _require_user(user_id)
    svc = MemoryService(session)
    summary = await svc.get_session(
        session_id=session_id,
        user_id=UUID(uid),
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(summary.id),
        "title": summary.title,
        "created_at": summary.created_at.isoformat(),
        "last_activity_at": summary.last_activity_at.isoformat(),
        "expires_at": summary.expires_at.isoformat(),
        "is_active": summary.is_active,
        "message_count": summary.message_count,
    }


@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: str | None = Depends(get_current_user),
):
    uid = _require_user(user_id)
    svc = MemoryService(session)
    success = await svc.expire_session(
        session_id=session_id,
        user_id=UUID(uid),
    )
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.commit()
    return {"status": "expired", "session_id": str(session_id)}
