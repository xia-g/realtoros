"""add_notifications: Create notifications table for push and polling.

Revision ID: 003
Revises: 002_add_leads_and_soft_delete
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "003_add_notifications"
down_revision: str | None = "002_add_leads_and_soft_delete"
branch_labels: str | None = None
depends_on: str | None = None


TABLE_NAME = "notifications"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(f"ix_{TABLE_NAME}_status", TABLE_NAME, ["status"])
    op.create_index(f"ix_{TABLE_NAME}_user_status", TABLE_NAME, ["user_id", "status"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE_NAME}_user_status", table_name=TABLE_NAME)
    op.drop_index(f"ix_{TABLE_NAME}_status", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
