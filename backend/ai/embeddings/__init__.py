"""Embedding pipeline — generate vector embeddings for documents and entities.

Model: multilingual-e5-small (384 dim)
Batch processing with deduplication by content_hash.
"""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.models.document_chunk import DocumentChunk
from backend.models.embedding import Embedding

logger = get_logger("knowledge")
EMBEDDING_DIM = 384


class EmbeddingPipeline:
    """Generate and store vector embeddings."""

    def __init__(self, session=None):
        self.session = session
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("intfloat/multilingual-e5-small")
            except ImportError:
                logger.warning("sentence-transformers not available, using stub")
        return self._model

    def _compute_hash(self, text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    async def embed_chunks(self, document_id: UUID) -> int:
        """Embed all chunks for a document. Deduplicates globally by content_hash."""
        if not self.session:
            return 0

        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return 0

        model = self._get_model()
        if model is None:
            return 0

        # Global existing hashes — any document, not just this document
        chunk_ids = [c.id for c in chunks]
        existing = await self.session.execute(
            select(Embedding.content_hash).where(Embedding.chunk_id.in_(chunk_ids))
        )
        local_hashes = {row[0] for row in existing.all()}

        # Also check global table to prevent same-content-across-documents dupes
        global_result = await self.session.execute(
            select(Embedding.content_hash).limit(10000)
        )
        global_hashes = {row[0] for row in global_result.all()}

        count = 0
        for chunk in chunks:
            content_hash = self._compute_hash(chunk.content)
            if content_hash in local_hashes or content_hash in global_hashes:
                continue

            vector = model.encode(chunk.content, normalize_embeddings=True)
            emb = Embedding(
                entity_type="document_chunk",
                entity_id=document_id,
                chunk_id=chunk.id,
                model_name="multilingual-e5-small",
                embedding=list(vector),
                content_hash=content_hash,
                token_count=chunk.token_count,
            )
            self.session.add(emb)
            local_hashes.add(content_hash)
            count += 1

        if count:
            await self.session.flush()

        logger.info("chunks_embedded", document_id=str(document_id), chunks=count)
        return count

    async def embed_text(self, text: str, entity_type: str, entity_id: UUID) -> Embedding | None:
        model = self._get_model()
        if model is None:
            return None

        content_hash = self._compute_hash(text)
        vector = model.encode(text, normalize_embeddings=True)
        emb = Embedding(
            entity_type=entity_type,
            entity_id=entity_id,
            model_name="multilingual-e5-small",
            embedding=list(vector),
            content_hash=content_hash,
        )
        if self.session:
            self.session.add(emb)
            await self.session.flush()
        return emb