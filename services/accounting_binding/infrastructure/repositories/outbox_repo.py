"""
Repository — Outbox.

Транзакционное хранение outbox-событий.
Нет repo.commit() — только UoW.commit().
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.events.outbox import OutboxEvent, OutboxEventType
from infrastructure.models.outbox_record import OutboxRecord


class OutboxRepository:
    """Репозиторий outbox-событий."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._buffer: list[OutboxEvent] = []

    async def push(self, event: OutboxEvent) -> None:
        """Добавить событие (в рамках UoW)."""
        record = OutboxRecord(
            event_type=event.event_type.name,
            document_id=event.document_id,
            payload_json=json.dumps(event.payload, ensure_ascii=False, default=str),
            correlation_json=json.dumps(event.correlation, ensure_ascii=False, default=str),
            status=event.status,
            created_at=datetime.utcnow(),
        )
        self._session.add(record)
        self._buffer.append(event)

    async def pull_pending(self, limit: int = 10) -> list[OutboxEvent]:
        """Забрать pending-события (worker)."""
        result = await self._session.execute(
            select(OutboxRecord)
            .where(OutboxRecord.status == "pending")
            .order_by(OutboxRecord.created_at)
            .limit(limit)
        )
        return [self._to_event(r) for r in result.scalars().all()]

    async def mark_sent(self, event_id: str) -> None:
        """Отметить как отправленное."""
        await self._session.execute(
            update(OutboxRecord)
            .where(OutboxRecord.id == event_id)
            .values(status="sent", sent_at=datetime.utcnow())
        )

    async def mark_failed(self, event_id: str, error: str) -> None:
        """Отметить как ошибочное."""
        await self._session.execute(
            update(OutboxRecord)
            .where(OutboxRecord.id == event_id)
            .values(status="failed", error=error)
        )

    def _to_event(self, record: OutboxRecord) -> OutboxEvent:
        return OutboxEvent(
            event_id=record.id,
            event_type=OutboxEventType[record.event_type],
            document_id=record.document_id,
            payload=json.loads(record.payload_json or "{}"),
            correlation=json.loads(record.correlation_json or "{}"),
            status=record.status,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
