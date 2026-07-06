"""Semantic search — hybrid BM25 + vector similarity ranking.

Methods:
- search_documents(query) — full-text + vector search across document_chunks
- search_clients(query) — search clients by name/phone with vector boost
- search_properties(query) — search properties by address with vector boost
- search_everything(query) — unified search across all entities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select, text

from backend.core.logging import get_logger

logger = get_logger("knowledge")


@dataclass
class SearchResult:
    entity_type: str
    entity_id: str
    title: str
    snippet: str
    score: float
    source: str  # vector or fulltext
    metadata: dict = field(default_factory=dict)


class KnowledgeSearchService:
    """Hybrid search: BM25 full-text + vector similarity."""

    def __init__(self, session=None):
        self.session = session
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("intfloat/multilingual-e5-small")
            except ImportError:
                pass
        return self._model

    async def search_documents(self, query: str, limit: int = 20) -> list[SearchResult]:
        return await self._search_entity("document_chunk", query, limit)

    async def search_clients(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await self._search_entity("client", query, limit)

    async def search_properties(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await self._search_entity("property", query, limit)

    async def search_everything(self, query: str, limit: int = 20) -> list[SearchResult]:
        results = []
        for entity_type in ["document_chunk", "client", "property", "deal", "lead"]:
            results.extend(await self._search_entity(entity_type, query, 10))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def _search_entity(self, entity_type: str, query: str, limit: int) -> list[SearchResult]:
        if not self.session:
            return []

        results = []

        # Method 1: Full-text search via document_chunks
        if entity_type == "document_chunk":
            from backend.models.document_chunk import DocumentChunk

            tsv = func.to_tsvector("russian", DocumentChunk.content)
            query_ts = func.plainto_tsquery("russian", query)
            stmt = (
                select(DocumentChunk, func.ts_rank(tsv, query_ts).label("rank"))
                .where(tsv.op("@@")(query_ts))
                .order_by(text("rank DESC"))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            for row in result.all():
                chunk = row[0]
                results.append(SearchResult(
                    entity_type="document",
                    entity_id=str(chunk.document_id),
                    title=f"Document chunk {chunk.chunk_index}",
                    snippet=chunk.content[:200],
                    score=float(row[1]) if row[1] else 0.0,
                    source="fulltext",
                ))

        # Method 2: Vector similarity (if embeddings available)
        model = self._get_model()
        if model and results:
            query_vec = model.encode(query, normalize_embeddings=True)

            from pgvector.sqlalchemy import Vector
            from backend.models.embedding import Embedding

            stmt = (
                select(Embedding, Embedding.embedding.cosine_distance(query_vec).label("distance"))
                .where(Embedding.entity_type == entity_type)
                .order_by(text("distance ASC"))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            for row in result.all():
                emb = row[0]
                vec_score = 1.0 - float(row[1]) if row[1] else 0.0
                # Merge with fulltext results (weighted)
                existing = next((r for r in results if r.entity_id == str(emb.entity_id)), None)
                if existing:
                    existing.score = existing.score * 0.3 + vec_score * 0.7
                    existing.source = "hybrid"
                else:
                    results.append(SearchResult(
                        entity_type=entity_type,
                        entity_id=str(emb.entity_id),
                        title=f"{entity_type} #{emb.entity_id}",
                        snippet="",
                        score=vec_score,
                        source="vector",
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]