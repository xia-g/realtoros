"""add_soft_delete_and_source_ref: Добавить deleted_at в 15 моделей + source_entity в graph.

Revision ID: 016
Revises: 015_add_deal_risk_assessments
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016_add_soft_delete_and_source_ref"
down_revision: str | None = "015_add_deal_risk_assessments"


def upgrade() -> None:
    # 1. GraphNode: add source_entity_type, source_entity_id, deleted_at
    op.add_column("graph_nodes", sa.Column("source_entity_type", sa.String(50), nullable=True))
    op.add_column("graph_nodes", sa.Column("source_entity_id", sa.UUID(), nullable=True))
    op.add_column("graph_nodes", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # created_at and updated_at already exist from migration 005
    op.create_index("ix_graph_nodes_source_entity", "graph_nodes", ["source_entity_type", "source_entity_id"])

    # 2. GraphEdge: add deleted_at, metadata
    # metadata already exists from migration 005
    op.add_column("graph_edges", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # created_at already exists from migration 005

    # 3. Soft delete для audit-таблиц
    for table in ["agent_tool_calls", "ai_call_log", "deal_checkpoints", "knowledge_messages", "knowledge_sessions"]:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 4. Soft delete для knowledge foundation
    for table in ["document_chunks", "embeddings"]:
        try:
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        except Exception:
            pass  # может уже существовать в некоторых версиях

    # 5. Soft delete для document_requirements, regulation, system_job, budget_usage, notification, lead_event
    for table in ["document_requirements", "regulations", "system_jobs", "budget_usage", "notifications", "lead_events"]:
        try:
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        except Exception:
            pass


def downgrade() -> None:
    # Reverse order
    for table in ["lead_events", "notifications", "budget_usage", "system_jobs", "regulations", "document_requirements"]:
        try:
            op.drop_column(table, "deleted_at")
        except Exception:
            pass
    for table in ["embeddings", "document_chunks"]:
        try:
            op.drop_column(table, "deleted_at")
        except Exception:
            pass
    for table in ["knowledge_sessions", "knowledge_messages", "deal_checkpoint", "ai_call_log", "agent_tool_calls"]:
        op.drop_column(table, "deleted_at")
    op.drop_column("graph_edges", "created_at")
    op.drop_column("graph_edges", "deleted_at")
    op.drop_column("graph_edges", "metadata")
    op.drop_index("ix_graph_nodes_source_entity", table_name="graph_nodes")
    op.drop_column("graph_nodes", "updated_at")
    op.drop_column("graph_nodes", "created_at")
    op.drop_column("graph_nodes", "deleted_at")
    op.drop_column("graph_nodes", "source_entity_id")
    op.drop_column("graph_nodes", "source_entity_type")
