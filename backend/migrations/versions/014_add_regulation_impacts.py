"""add_regulation_impacts: AI-анализ изменений нормативных актов.

Revision ID: 014
Revises: 013_add_regulation_versions_and_sync
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "014_add_regulation_impacts"
down_revision: str | None = "013_add_regulation_versions_and_sync"


def upgrade() -> None:
    op.create_table(
        "regulation_impacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("affected_deals_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("affected_templates_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("affected_workflows_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("affected_requirements_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("affected_deal_ids", postgresql.JSONB(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommendations", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["regulation_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulation_impacts_version_id", "regulation_impacts", ["version_id"])


def downgrade() -> None:
    op.drop_table("regulation_impacts")
