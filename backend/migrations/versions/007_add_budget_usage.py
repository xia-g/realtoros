"""add_budget_usage: Create budget_usage table for cross-process cost tracking.

Revision ID: 007
Revises: 006_add_ai_call_log
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007_add_budget_usage"
down_revision: str | None = "006_add_ai_call_log"
branch_labels: str | None = None
depends_on: str | None = None

TABLE = "budget_usage"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("day", sa.Date, nullable=False, index=True),
        sa.Column("spent_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("provider", sa.String(50), nullable=True),
    )

    op.create_index(f"ix_{TABLE}_user_day", TABLE, ["user_id", "day"], unique=True,
                    postgresql_where=sa.text("user_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_user_day", table_name=TABLE)
    op.drop_table(TABLE)
