"""KnowledgeRuntimeService — orchestrates semantic indexing pipeline.

Delegates to:
  - GraphLifecycleService — create/update GraphNode
  - EmbeddingPipeline — generate vector embeddings
  - Search index update — (minimal log for Phase 1)

Design decisions:
  - Two transaction boundaries: graph sync (commit) → embedding (commit)
  - Service, not repository: orchestrates, does not manage data directly
  - Consumer is only delegation: no SQL, no embedding, no graph mutation
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from backend.ai.embeddings import EmbeddingPipeline
from backend.models.document import Document
from backend.models.document_chunk import DocumentChunk
from backend.services.graph_lifecycle_service import GraphLifecycleService
from backend.services.knowledge_runtime.document_projection_layer import _load_document_from_intake
from backend.services.knowledge_runtime.payload import DocumentReadyPayload

logger = get_logger(__name__)


class KnowledgeRuntimeService:
    """Orchestrates semantic indexing: graph node + embeddings + search index.

    Does NOT contain SQL, embedding generation, or graph mutation logic directly.
    Everything is delegated to specialized services.
    Consumer is a thin delegation layer — this service is the orchestrator.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def process(self, payload: DocumentReadyPayload) -> None:
        """Process a document.ready event end-to-end.

        Transaction boundaries:
          1. Graph sync & document load (own transaction, committed)
          2. Embedding generation (separate session, committed independently)
          3. Search index (minimal log — full search rewrite out of scope)

        If graph sync fails, embedding is NOT executed.
        If embedding fails, graph node is already saved (acceptable for Phase 1).
        """
        document_id = payload.document_id

        # Step 1-3: Load document, chunks, sync graph (own transaction)
        async with self._session_factory() as session:
            doc = await self._load_document(session, document_id)
            if doc is None:
                logger.warning(
                    "knowledge_runtime_document_not_found",
                    document_id=str(document_id),
                )
                return

            await self._ensure_chunks(session, doc)
            await self._sync_graph_node(session, doc, payload)
            await session.commit()

        # Step 4: Embed chunks (separate session — may be long-running)
        async with self._session_factory() as session:
            try:
                pipeline = EmbeddingPipeline(session=session)
                count = await pipeline.embed_chunks(document_id)
                await session.commit()
                logger.info(
                    "knowledge_runtime_embedding_completed",
                    document_id=str(document_id),
                    chunks_count=count,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "knowledge_runtime_embedding_failed",
                    document_id=str(document_id),
                )
                raise

        # Step 5: Search index (minimal log — full FTS refresh out of scope)
        logger.info(
            "search_index_update",
            document_id=str(document_id),
        )
        logger.info(
            "knowledge_runtime_completed",
            document_id=str(document_id),
        )

    async def _load_document(
        self,
        session: AsyncSession,
        document_id: UUID,
    ) -> Document | None:
        """Load a document by ID from document_intake (temporary compatibility layer)."""
        return await _load_document_from_intake(session, document_id)

    async def _ensure_chunks(
        self,
        session: AsyncSession,
        doc: Document,
    ) -> list[DocumentChunk]:
        """Load chunks for a document — warn if none exist."""
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            logger.warning(
                "knowledge_runtime_no_chunks",
                document_id=str(doc.id),
            )
        return chunks

    async def _sync_graph_node(
        self,
        session: AsyncSession,
        doc: Document,
        payload: DocumentReadyPayload,
    ) -> None:
        """Sync document as a graph node via GraphLifecycleService."""
        svc = GraphLifecycleService(session=session)
        await svc.sync_entity(
            entity_type="document",
            entity_id=doc.id,
            title=doc.title or "document",
            metadata={
                "document_id": str(doc.id),
                "profile": payload.profile,
                "source": "knowledge_runtime",
            },
        )
