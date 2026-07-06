"""add_regulations: Regulatory knowledge base.

Revision ID: 010
Revises: 009_add_deal_checkpoints_and_doc_reqs
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "010_add_regulations"
down_revision: str | None = "009_add_deal_checkpoints_and_doc_reqs"


def upgrade() -> None:
    op.create_table(
        "regulations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("trust_level", sa.String(20), nullable=False, server_default=sa.text("'OFFICIAL'")),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("regulation_type", sa.String(30), nullable=False, server_default=sa.text("'law'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "hash", name="uq_regulation_source_hash"),
    )
    op.create_index("ix_regulations_source", "regulations", ["source"])
    op.create_index("ix_regulations_trust_level", "regulations", ["trust_level"])
    op.create_index("ix_regulations_hash", "regulations", ["hash"])
    op.create_index("ix_regulations_category", "regulations", ["category"])


def downgrade() -> None:
    op.drop_table("regulations")
