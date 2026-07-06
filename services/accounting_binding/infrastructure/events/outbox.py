"""
Infrastructure — Outbox для posting и событий.

Transactional outbox pattern:
1. approve → persist accounting_document + outbox_event (same TX)
2. worker → read outbox → post
3. worker → mark as sent

Гарантия: at-least-once delivery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Protocol
from uuid import uuid4


class OutboxEventType(Enum):
    """Типы событий outbox."""
    DOCUMENT_READY = auto()
    DOCUMENT_APPROVED = auto()
    POSTING_REQUESTED = auto()
    POSTING_COMPLETED = auto()
    POSTING_REVERSED = auto()
    REPORT_REBUILT = auto()
    REPLAY_REQUESTED = auto()


@dataclass
class OutboxEvent:
    """Событие outbox."""
    event_id: str = ""
    event_type: OutboxEventType = OutboxEventType.DOCUMENT_READY
    document_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    correlation: dict[str, str] = field(default_factory=dict)
    status: str = "pending"  # pending → sent → failed
    created_at: str = ""
    sent_at: str | None = None

    @classmethod
    def create(
        cls,
        event_type: OutboxEventType,
        document_id: str,
        payload: dict[str, Any] | None = None,
        correlation: dict[str, str] | None = None,
    ) -> "OutboxEvent":
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            document_id=document_id,
            payload=payload or {},
            correlation=correlation or {},
            status="pending",
            created_at=datetime.utcnow().isoformat(),
        )


class OutboxRepository(Protocol):
    """Хранилище outbox-событий."""
    async def push(self, event: OutboxEvent) -> None: ...
    async def pull_pending(self, limit: int = 10) -> list[OutboxEvent]: ...
    async def mark_sent(self, event_id: str) -> None: ...
    async def mark_failed(self, event_id: str, error: str) -> None: ...


class Outbox:
    """Outbox — транзакционная отправка событий.
    
    Использование:
        async with outbox.transaction():
            await repo.save(document)
            await outbox.emit(OutboxEventType.DOCUMENT_APPROVED, doc_id)
    """

    def __init__(self, repo: OutboxRepository | None = None):
        self._repo = repo
        self._buffer: list[OutboxEvent] = []

    async def emit(
        self,
        event_type: OutboxEventType,
        document_id: str,
        payload: dict[str, Any] | None = None,
        correlation: dict[str, str] | None = None,
    ) -> None:
        """Добавить событие в outbox."""
        event = OutboxEvent.create(event_type, document_id, payload, correlation)
        if self._repo:
            await self._repo.push(event)
        self._buffer.append(event)

    async def flush(self) -> list[OutboxEvent]:
        """Отправить накопленные события."""
        sent = list(self._buffer)
        self._buffer.clear()
        return sent
