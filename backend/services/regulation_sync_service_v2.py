"""Regulation Sync Service V2 — реальная синхронизация с источниками."""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from structlog import get_logger
from backend.integrations.regulations.adapter_registry import AdapterRegistry
from backend.core.domain_events import DomainEvent, get_event_bus
logger = get_logger(__name__)

class RegulationSyncServiceV2:
    def __init__(self, session=None):
        self.session = session
        self._event_bus = get_event_bus()

    async def sync_source(self, source_code: str, source_type: str, correlation_id: str = "") -> dict:
        adapter = AdapterRegistry.get_adapter(source_type)
        result = await adapter.fetch_updates()
        logger.info("sync_source_completed", source=source_code, docs=len(result.documents), correlation_id=correlation_id)
        for doc in result.documents:
            await self._event_bus.emit(DomainEvent(
                event_type="regulation.updated",
                entity_type="regulation",
                entity_id=uuid4(),
                correlation_id=correlation_id,
                payload=doc,
            ))
        return {"source": source_code, "documents_found": len(result.documents), "status": "completed"}

    async def sync_all_sources(self, correlation_id: str = "") -> list[dict]:
        sources = AdapterRegistry.list_available()
        results = []
        for src_type in sources:
            try:
                r = await self.sync_source(src_type, src_type, correlation_id)
                results.append(r)
            except Exception as e:
                logger.error("sync_source_failed", source=src_type, error=str(e))
                results.append({"source": src_type, "status": "failed", "error": str(e)})
        return results