"""add_memory_layer: Create knowledge_sessions + knowledge_messages tables.

Revision ID: 008
Revises: 007_add_budget_usage
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008_add_memory_layer"
down_revision: str | None = "007_add_budget_usage"
branch_labels: str | None = None
depends_on: str | None = None

SESSIONS = "knowledge_sessions"
MESSAGES = "knowledge_messages"


def upgrade() -> None:
    # ── knowledge_sessions ──
    op.create_table(
        SESSIONS,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_index(
        "idx_knowledge_sessions_user",
        SESSIONS,
        ["user_id"],
    )
    op.create_index(
        "idx_knowledge_sessions_active",
        SESSIONS,
        ["is_active", "user_id"],
    )
    op.create_index(
        "idx_knowledge_sessions_expiry",
        SESSIONS,
        ["expires_at"],
        postgresql_where=sa.text("is_active = true"),
    )

    op.execute(sa.text("COMMENT ON TABLE knowledge_sessions IS 'Knowledge Agent conversational memory sessions'"))
    op.execute(sa.text("COMMENT ON COLUMN knowledge_sessions.user_id IS 'Owner of this session — NEVER trust session_id without user_id filter'"))
    op.execute(sa.text("COMMENT ON COLUMN knowledge_sessions.expires_at IS 'Session TTL — 24h from last_activity_at'"))

    # ── knowledge_messages ──
    op.create_table(
        MESSAGES,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_index(
        "idx_knowledge_messages_session",
        MESSAGES,
        ["session_id"],
    )
    op.create_index(
        "idx_knowledge_messages_created",
        MESSAGES,
        ["session_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_knowledge_messages_session",
        MESSAGES,
        SESSIONS,
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(sa.text("COMMENT ON TABLE knowledge_messages IS 'Messages within a knowledge session'"))
    op.execute(sa.text("COMMENT ON COLUMN knowledge_messages.role IS 'One of: user, assistant, system'"))
    op.execute(sa.text("COMMENT ON COLUMN knowledge_messages.token_count IS 'Token count of content for budget tracking'"))


def downgrade() -> None:
    op.drop_table(MESSAGES)
    op.drop_table(SESSIONS)
