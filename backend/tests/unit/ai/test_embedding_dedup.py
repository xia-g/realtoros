"""Tests for EmbeddingPipeline deduplication."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from uuid_extensions import uuid7


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def pipeline(mock_session):
    from backend.ai.embeddings import EmbeddingPipeline
    pipe = EmbeddingPipeline(mock_session)
    pipe._model = MagicMock()
    pipe._model.encode = MagicMock(return_value=[0.1] * 384)
    return pipe


class TestDeduplication:
    async def test_global_dedup_prevents_same_hash(self, pipeline):
        """Same content_hash across different documents should be skipped."""
        doc_id = uuid7()
        pipeline.session.execute.return_value.scalars.return_value.all = MagicMock(return_value=[])
        pipeline.session.execute.return_value.all = MagicMock(return_value=[("existing_hash",)])

        from backend.models.document_chunk import DocumentChunk
        chunk = DocumentChunk(
            document_id=doc_id, chunk_index=0,
            content="Duplicate text content",
        )
        chunk.id = uuid7()

        with patch.object(pipeline, "_compute_hash", return_value="existing_hash"):
            count = await pipeline.embed_chunks(doc_id)
            assert count == 0, "Should skip duplicate content hash"