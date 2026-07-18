"""add_soft_delete_consistency: Add deleted_at to analytics tables.

Resolves C1 from Sprint 8.7 audit.
Note: deals and deal_participants already have deleted_at from earlier migrations.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "022_add_soft_delete_consistency"
down_revision: str | None = "021_add_analytics_foundation"


def upgrade() -> None:
    for table in ["analytics_snapshots", "analytics_alerts", "prediction_results"]:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])


def downgrade() -> None:
    for table in ["prediction_results", "analytics_alerts", "analytics_snapshots"]:
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")
