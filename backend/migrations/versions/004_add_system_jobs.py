"""add_system_jobs: Create system_jobs table for scheduled background tasks.

Revision ID: 004
Revises: 003_add_notifications
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_add_system_jobs"
down_revision: str | None = "003_add_notifications"
branch_labels: str | None = None
depends_on: str | None = None

TABLE = "system_jobs"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("task_type", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("trigger", sa.String(50), nullable=False, server_default="once"),
        sa.Column("trigger_args", postgresql.JSONB, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(f"ix_{TABLE}_status_priority", TABLE, ["status", "priority"])
    op.create_index(f"ix_{TABLE}_task_status", TABLE, ["task_type", "status"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_task_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_status_priority", table_name=TABLE)
    op.drop_table(TABLE)
