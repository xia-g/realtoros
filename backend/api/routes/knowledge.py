"""Knowledge API — semantic search, graph queries, pipeline management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.api.dependencies import get_session
from backend.ai.search import KnowledgeSearchService
from backend.models.graph_node import GraphNode
from backend.models.graph_edge import GraphEdge
from backend.models.document import Document

router = APIRouter()


@router.post("/search")
async def search_knowledge(
    query: str = Query(..., min_length=1),
    entity_type: str | None = Query(None),
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_session),
):
    svc = KnowledgeSearchService(session)
    if entity_type == "documents":
        results = await svc.search_documents(query, limit)
    elif entity_type == "clients":
        results = await svc.search_clients(query, limit)
    elif entity_type == "properties":
        results = await svc.search_properties(query, limit)
    else:
        results = await svc.search_everything(query, limit)

    return [
        {
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "title": r.title,
            "snippet": r.snippet,
            "score": round(r.score, 4),
            "source": r.source,
        }
        for r in results
    ]


@router.get("/document/{document_id}")
async def get_document_knowledge(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    from backend.repositories import DocumentRepository
    repo = DocumentRepository(session)
    doc = await repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/graph/entity/{entity_id}")
async def get_entity_graph(
    entity_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    # Find node by entity_id
    result = await session.execute(
        select(GraphNode).where(GraphNode.entity_id == entity_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Entity not found in graph")

    # Get edges
    edge_result = await session.execute(
        select(GraphEdge).where(
            (GraphEdge.source_node_id == node.id) | (GraphEdge.target_node_id == node.id)
        )
    )
    edges = edge_result.scalars().all()

    # Get connected nodes
    connected_ids = set()
    for e in edges:
        connected_ids.add(str(e.source_node_id))
        connected_ids.add(str(e.target_node_id))

    return {
        "node": {
            "id": str(node.id),
            "type": node.node_type,
            "entity_id": str(node.entity_id),
            "title": node.title,
        },
        "edges": [
            {
                "id": str(e.id),
                "type": e.edge_type,
                "source": str(e.source_node_id),
                "target": str(e.target_node_id),
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }


@router.post("/rebuild")
async def rebuild_knowledge_graph(session: AsyncSession = Depends(get_session)):
    from backend.ai.graph import KnowledgeGraphBuilder
    builder = KnowledgeGraphBuilder(session)
    result = await builder.build_full()
    return {"status": "ok", "nodes": result["nodes"], "edges": result["edges"]}


@router.get("/stats")
async def knowledge_stats(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(GraphNode).count())
    nodes = result.scalar() or 0
    result = await session.execute(select(GraphEdge).count())
    edges = result.scalar() or 0
    from backend.models.embedding import Embedding
    result = await session.execute(select(Embedding).count())
    embeddings = result.scalar() or 0
    from backend.models.document_chunk import DocumentChunk
    result = await session.execute(select(DocumentChunk).count())
    chunks = result.scalar() or 0

    return {
        "graph_nodes": nodes,
        "graph_edges": edges,
        "embeddings": embeddings,
        "document_chunks": chunks,
        "embedding_dim": 384,
        "model": "multilingual-e5-small",
    }