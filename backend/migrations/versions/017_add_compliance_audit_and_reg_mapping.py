"""add_compliance_audit_and_reg_mapping: Audit trail + regulation linkage.

Revision ID: 017
Revises: 016_add_soft_delete_and_source_ref
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "017_add_compliance_audit_and_reg_mapping"
down_revision: str | None = "016_add_soft_delete_and_source_ref"


def upgrade() -> None:
    # compliance_audits
    op.create_table(
        "compliance_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("audit_type", sa.String(30), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("blocking_issues", postgresql.JSONB(), nullable=True),
        sa.Column("used_regulations", postgresql.JSONB(), nullable=True),
        sa.Column("used_documents", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_audits_deal_id", "compliance_audits", ["deal_id"])
    op.create_index("ix_compliance_audits_correlation_id", "compliance_audits", ["correlation_id"])
    op.create_index("ix_compliance_audits_audit_type", "compliance_audits", ["audit_type"])
    op.create_index("ix_compliance_audits_created_at", "compliance_audits", ["created_at"])

    # regulation_requirement_mappings
    op.create_table(
        "regulation_requirement_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.UUID(), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("checkpoint_key", sa.String(100), nullable=False),
        sa.Column("article", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["regulation_id"], ["regulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("regulation_id", "document_type", "checkpoint_key", name="uq_reg_requirement_mapping"),
    )
    op.create_index("ix_reg_requirement_mapping_regulation_id", "regulation_requirement_mappings", ["regulation_id"])


def downgrade() -> None:
    op.drop_table("regulation_requirement_mappings")
    op.drop_table("compliance_audits")
