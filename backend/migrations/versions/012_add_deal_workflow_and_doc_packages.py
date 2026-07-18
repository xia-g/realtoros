"""add_deal_workflow_and_doc_packages: Stage transitions and document packages.

Revision ID: 012
Revises: 011_add_agent_tool_calls
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012_add_deal_workflow_and_doc_packages"
down_revision: str | None = "011_add_agent_tool_calls"


def upgrade() -> None:
    # deal_workflows
    op.create_table(
        "deal_workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("workflow_type", sa.String(50), nullable=False, server_default=sa.text("'SALE_APARTMENT'")),
        sa.Column("current_stage", sa.String(50), nullable=False, server_default=sa.text("'LEAD'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_workflows_deal_id", "deal_workflows", ["deal_id"])

    # deal_stage_transitions
    op.create_table(
        "deal_stage_transitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("from_stage", sa.String(50), nullable=False),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("transitioned_by", sa.UUID(), nullable=True),
        sa.Column("conditions_met", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["deal_workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transitioned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_stage_transitions_workflow_id", "deal_stage_transitions", ["workflow_id"])

    # deal_document_packages
    op.create_table(
        "deal_document_packages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("requirement_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'missing'")),
        sa.Column("attached_by", sa.UUID(), nullable=True),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["document_requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["attached_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "requirement_id", name="uq_deal_doc_requirement"),
    )
    op.create_index("ix_deal_document_packages_deal_id", "deal_document_packages", ["deal_id"])


def downgrade() -> None:
    op.drop_table("deal_document_packages")
    op.drop_table("deal_stage_transitions")
    op.drop_table("deal_workflows")
