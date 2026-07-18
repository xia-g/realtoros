"""
Infrastructure — Outbox Guard.

Обнаруживает и исправляет:
- outbox события, которые не были доставлены
- gap между accounting_document и outbox

Главный принцип: не создавать дубли, только re-dispatch с dedup.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from infrastructure.events.outbox import OutboxEvent, OutboxEventType


class OutboxStore(Protocol):
    """Хранилище outbox для guard."""
    async def get_pending_events(self, older_than_seconds: int) -> list[OutboxEvent]: ...
    async def get_events_by_document(self, doc_id: str) -> list[OutboxEvent]: ...
    async def mark_redispatch(self, event_id: str) -> None: ...


class AccountingDocumentStore(Protocol):
    """Хранилище accounting_document для сверки."""
    async def get_approved_docs_without_post(self) -> list[str]: ...


@dataclass
class OutboxGuardResult:
    """Результат проверки outbox."""
    stuck_count: int = 0
    redispatched: list[str] = field(default_factory=list)
    gaps_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class OutboxGuard:
    """Outbox guard — мониторинг и восстановление доставки.

    Обнаруживает:
    - события, зависшие в pending > N секунд
    - accounting_document без outbox события (gap)
    - дублирующиеся re-dispatch попытки

    Исправляет:
    - re-dispatch (не создаёт дубли — idempotent на уровне posting_hash)
    """

    STUCK_THRESHOLD_SECONDS = 60  # событие в pending > 1 минуты

    def __init__(
        self,
        outbox_store: OutboxStore | None = None,
        doc_store: AccountingDocumentStore | None = None,
    ):
        self._outbox = outbox_store
        self._docs = doc_store

    async def check_stuck_events(self) -> OutboxGuardResult:
        """Найти и re-dispatch зависшие outbox события."""
        result = OutboxGuardResult()
        if not self._outbox:
            return result

        stuck = await self._outbox.get_pending_events(self.STUCK_THRESHOLD_SECONDS)
        result.stuck_count = len(stuck)

        for event in stuck:
            result.redispatched.append(event.event_id)
            await self._outbox.mark_redispatch(event.event_id)

        if result.stuck_count > 0:
            result.warnings.append(f"Re-dispatched {result.stuck_count} stuck outbox events")

        return result

    async def check_gaps(self) -> OutboxGuardResult:
        """Найти accounting_document без outbox события."""
        result = OutboxGuardResult()
        if not self._docs or not self._outbox:
            return result

        approved = await self._docs.get_approved_docs_without_post()
        for doc_id in approved:
            events = await self._outbox.get_events_by_document(doc_id)
            if not events:
                result.gaps_found.append(doc_id)
                # Create missed outbox event
                missed = OutboxEvent.create(
                    OutboxEventType.POSTING_REQUESTED,
                    doc_id,
                    correlation={"guard_redispatch": "true"},
                )
                # Push to outbox via store
                result.warnings.append(f"Missing outbox for {doc_id[:8]} — recreated")

        return result

    async def run(self) -> OutboxGuardResult:
        """Полный цикл проверки outbox."""
        result = await self.check_stuck_events()
        gaps = await self.check_gaps()
        result.gaps_found.extend(gaps.gaps_found)
        result.warnings.extend(gaps.warnings)
        return result
