"""Notification API endpoints — polling, delivery status, manual creation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.services.notification_service import NotificationService

router = APIRouter()


@router.get("/pending")
async def get_pending_notifications(
    since: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    svc = NotificationService(session)
    notifs = await svc.get_pending(since=since)
    return [
        {
            "id": str(n.id),
            "user_id": str(n.user_id),
            "notification_type": n.notification_type,
            "title": n.title,
            "body": n.body,
            "payload": n.payload,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]


@router.post("/{notification_id}/delivered")
async def mark_delivered(notification_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = NotificationService(session)
    await svc.mark_delivered(notification_id)
    return {"status": "ok"}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = NotificationService(session)
    await svc.mark_read(notification_id)
    return {"status": "ok"}
