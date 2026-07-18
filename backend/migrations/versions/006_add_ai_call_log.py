"""add_ai_call_log: Create ai_call_log table for LLM cost tracking.

Revision ID: 006
Revises: 005_add_knowledge_foundation
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_add_ai_call_log"
down_revision: str | None = "005_add_knowledge_foundation"
branch_labels: str | None = None
depends_on: str | None = None

TABLE = "ai_call_log"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("correlation_id", sa.String(16), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(f"ix_{TABLE}_created", TABLE, [sa.text("created_at DESC")])
    op.create_index(f"ix_{TABLE}_user", TABLE, ["user_id", sa.text("created_at DESC")])
    op.create_index(f"ix_{TABLE}_provider", TABLE, ["provider", sa.text("created_at DESC")])
    op.create_index(f"ix_{TABLE}_correlation", TABLE, ["correlation_id"])

    # Partition readiness comment
    op.execute("COMMENT ON TABLE ai_call_log IS 'd6d/ai-call-log; partition threshold: 5M rows; strategy: monthly by created_at'")


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_correlation", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_provider", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_created", table_name=TABLE)
    op.drop_table(TABLE)