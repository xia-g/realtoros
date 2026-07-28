"""KnowledgeRuntimeConsumer — consumes document.ready → semantic indexing.

Consumes document.ready events, orchestrates:
  1. Load document from DB
  2. Sync graph node (GraphLifecycleService)
  3. Embed chunks (EmbeddingPipeline)
  4. Search index update (minimal)

Key design points:
  - Extends BaseConsumer — inherits idempotent dedup via ConsumerStateRepository
  - Delegates ALL logic to KnowledgeRuntimeService
  - Consumer contains NO SQL, NO embedding generation, NO graph mutation
  - Two transaction boundaries: graph sync → embedding (separate sessions)
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker
from structlog import get_logger

from backend.core.integration_event import IntegrationEvent
from backend.infrastructure.consumer_base import (
    BaseConsumer,
)
from backend.services.knowledge_runtime.payload import DocumentReadyPayload
from backend.services.knowledge_runtime.service import KnowledgeRuntimeService

logger = get_logger(__name__)


class KnowledgeRuntimeConsumer(BaseConsumer):
    """Consumes document.ready → delegates to KnowledgeRuntimeService.

    Consumer is a thin orchestration layer. It does NOT contain:
      - SQL queries (load document, chunks)
      - Embedding generation
      - Graph mutations

    Everything is delegated to KnowledgeRuntimeService.
    """

    consumer_name = "knowledge_runtime"

    def __init__(
        self,
        dsn: str,
        session_factory: async_sessionmaker,
    ) -> None:
        super().__init__(consumer_name=self.consumer_name, dsn=dsn)
        self._service = KnowledgeRuntimeService(session_factory)

    async def _process(self, event: IntegrationEvent) -> None:
        """Process a document.ready event.

        Args:
            event: IntegrationEvent with payload containing
                   profile data. document_id comes from aggregate_id.
        """
        # event.payload may contain 'status', 'profile' etc.
        # DocumentReadyPayload expects: document_id, profile, source
        # Use aggregate_id as document_id (document UUID stored in outbox row)
        payload = DocumentReadyPayload(
            document_id=event.aggregate_id,
            profile=event.payload.get("profile", {}),
        )
        await self._service.process(payload)
