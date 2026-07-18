"""add_regulation_versions_and_sync: Regulation versioning and sync jobs.

Revision ID: 013
Revises: 012_add_deal_workflow_and_doc_packages
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013_add_regulation_versions_and_sync"
down_revision: str | None = "012_add_deal_workflow_and_doc_packages"


def upgrade() -> None:
    op.create_table(
        "regulation_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["regulation_id"], ["regulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regulation_id", "version", name="uq_regulation_version"),
    )
    op.create_index("ix_regulation_versions_regulation_id", "regulation_versions", ["regulation_id"])

    op.create_table(
        "regulation_sync_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("items_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulation_sync_jobs_source", "regulation_sync_jobs", ["source"])


def downgrade() -> None:
    op.drop_table("regulation_sync_jobs")
    op.drop_table("regulation_versions")
