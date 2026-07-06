"""add_analytics_foundation: Snapshots, alerts, predictions.

Revision ID: 021
Revises: 020_add_deal_operations
Create Date: 2026-06-09
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021_add_analytics_foundation"
down_revision: str | None = "020_add_deal_operations"


def upgrade() -> None:
    op.create_table("analytics_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("snapshot_type", sa.String(50), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_analytics_snapshots_type", "analytics_snapshots", ["snapshot_type"])
    op.create_index("ix_analytics_snapshots_date", "analytics_snapshots", ["snapshot_date"])

    op.create_table("analytics_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_analytics_alerts_severity", "analytics_alerts", ["severity"])
    op.create_index("ix_analytics_alerts_type", "analytics_alerts", ["alert_type"])
    op.create_index("ix_analytics_alerts_created", "analytics_alerts", ["created_at"])

    op.create_table("prediction_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("prediction_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_prediction_results_type", "prediction_results", ["prediction_type"])
    op.create_index("ix_prediction_results_entity", "prediction_results", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("prediction_results")
    op.drop_table("analytics_alerts")
    op.drop_table("analytics_snapshots")
