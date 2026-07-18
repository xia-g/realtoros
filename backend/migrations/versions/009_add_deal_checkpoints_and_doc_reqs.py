"""add_deal_checkpoints_and_doc_reqs: Deal checklist foundation.

Revision ID: 009
Revises: 008_add_memory_layer
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "009_add_deal_checkpoints_and_doc_reqs"
down_revision: str | None = "008_add_memory_layer"


def upgrade() -> None:
    # ── deal_checkpoints ──
    op.create_table(
        "deal_checkpoints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("checkpoint_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "checkpoint_key", name="uq_deal_checkpoint_key"),
    )
    op.create_index("ix_deal_checkpoints_deal_id", "deal_checkpoints", ["deal_id"])
    op.create_index("ix_deal_checkpoints_stage", "deal_checkpoints", ["stage"])
    op.create_index("ix_deal_checkpoints_checkpoint_key", "deal_checkpoints", ["checkpoint_key"])

    # ── document_requirements ──
    op.create_table(
        "document_requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_type", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("regulation_ref", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_type", "document_type", name="uq_deal_type_doc_type"),
    )
    op.create_index("ix_document_requirements_deal_type", "document_requirements", ["deal_type"])
    op.create_index("ix_document_requirements_document_type", "document_requirements", ["document_type"])


def downgrade() -> None:
    op.drop_table("document_requirements")
    op.drop_table("deal_checkpoints")
