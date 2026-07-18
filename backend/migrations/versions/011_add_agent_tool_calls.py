"""add_agent_tool_calls: Audit log for Agent Runtime tool calls.

Revision ID: 011
Revises: 010_add_regulations
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "011_add_agent_tool_calls"
down_revision: str | None = "010_add_regulations"


def upgrade() -> None:
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["knowledge_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_correlation_id", "agent_tool_calls", ["correlation_id"])
    op.create_index("ix_agent_tool_calls_session_id", "agent_tool_calls", ["session_id"])
    op.create_index("ix_agent_tool_calls_user_id", "agent_tool_calls", ["user_id"])
    op.create_index("ix_agent_tool_calls_tool_name", "agent_tool_calls", ["tool_name"])
    op.create_index("ix_agent_tool_calls_created_at", "agent_tool_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_tool_calls")
