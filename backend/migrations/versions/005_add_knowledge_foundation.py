"""add_knowledge_foundation: embeddings, document_chunks, graph_nodes, graph_edges.

Revision ID: 005
Revises: 004_add_system_jobs
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_add_knowledge_foundation"
down_revision: str | None = "004_add_system_jobs"
branch_labels: str | None = None
depends_on: str | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── embeddings ──
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(100), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=False),  # will be cast to vector
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(%d) USING embedding::vector(%d)" % (EMBEDDING_DIM, EMBEDDING_DIM))
    op.create_index("ix_embeddings_hnsw", "embeddings", ["embedding"], postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_index("ix_embeddings_ivfflat", "embeddings", ["embedding"], postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"})

    # ── document_chunks ──
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── graph_nodes ──
    op.create_table(
        "graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("node_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── graph_edges ──
    op.create_table(
        "graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("edge_type", sa.String(50), nullable=False, index=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Composite indexes ──
    op.create_index("ix_document_chunks_doc_chunk", "document_chunks", ["document_id", "chunk_index"], unique=True)
    op.create_index("ix_graph_nodes_type_entity", "graph_nodes", ["node_type", "entity_id"], unique=True)
    op.create_index("ix_graph_edges_source_type", "graph_edges", ["source_node_id", "edge_type"])
    op.create_index("ix_graph_edges_target_type", "graph_edges", ["target_node_id", "edge_type"])


def downgrade() -> None:
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_table("document_chunks")
    op.drop_table("embeddings")