"""Notification service — create, poll, and manage user notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.core.logging import get_logger
from backend.repositories.notification_repository import NotificationRepository

logger = get_logger("app")


class NotificationService:
    def __init__(self, session):
        self.session = session
        self.repo = NotificationRepository(session)

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        body: str | None = None,
        payload: dict | None = None,
    ):
        notif = await self.repo.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            payload=payload,
        )
        logger.info(
            "notification_created",
            notification_id=str(notif.id),
            user_id=str(user_id),
            notification_type=notification_type,
        )
        return notif

    async def get_pending(self, since: datetime | None = None) -> list:
        return await self.repo.get_pending_since(since)

    async def mark_delivered(self, notification_id: UUID) -> None:
        await self.repo.mark_delivered(notification_id)

    async def mark_read(self, notification_id: UUID) -> None:
        await self.repo.mark_read(notification_id)
