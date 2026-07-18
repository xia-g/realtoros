"""Notification repository.

Handles creation, polling, and status updates for notifications.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update

from backend.models.notification import Notification
from backend.repositories.base import GenericRepository


class NotificationRepository(GenericRepository[Notification]):
    def __init__(self, session):
        super().__init__(session, Notification)

    async def get_pending_since(self, since: datetime | None = None) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.status == "pending")
            .order_by(Notification.created_at.asc())
            .limit(50)
        )
        if since:
            stmt = stmt.where(Notification.created_at > since)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_delivered(self, notification_id: UUID) -> None:
        await self.update(notification_id, status="delivered", sent_at=datetime.now(timezone.utc))

    async def mark_read(self, notification_id: UUID) -> None:
        await self.update(notification_id, status="read", read_at=datetime.now(timezone.utc))

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        body: str | None = None,
        payload: dict | None = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            payload=payload,
            status="pending",
        )
        self.session.add(notif)
        await self.session.flush()
        return notif
