"""
Alembic — forward-only migration.

Правила:
- upgrade() — только CREATE/ALTER/INSERT
- downgrade() — НЕТ (запрещён)
- Rollback через новую миграцию + rebuild projection
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Initial schema for Accounting Binding."""
    op.create_table(
        "accounting_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), default=""),
        sa.Column("trace_id", sa.String(64), default=""),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("process_state", sa.String(20), default="pending"),
        sa.Column("approval_required", sa.String(20), default="auto"),
        sa.Column("entries_json", sa.Text, default="[]"),
        sa.Column("tax_entries_json", sa.Text, default="[]"),
        sa.Column("total_debit", sa.Numeric(16, 2), default=0),
        sa.Column("total_credit", sa.Numeric(16, 2), default=0),
        sa.Column("mapping_hash", sa.String(32), index=True),
        sa.Column("approval_revision", sa.Integer, default=0),
        sa.Column("approved_mapping_hash", sa.String(32), default=""),
        sa.Column("pipeline_run_id", sa.String(36), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("accounting_document_id", sa.String(36), nullable=False, index=True),
        sa.Column("company_id", sa.String(36), nullable=False, index=True),
        sa.Column("document_date", sa.String(10), default=""),
        sa.Column("lines_json", sa.Text, default="[]"),
        sa.Column("total_debit", sa.Numeric(16, 2), default=0),
        sa.Column("total_credit", sa.Numeric(16, 2), default=0),
        sa.Column("posting_hash", sa.String(64), unique=True),
        sa.Column("process_state", sa.String(20), default="completed"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by", sa.String(64), default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("payload_json", sa.Text, default="{}"),
        sa.Column("correlation_json", sa.Text, default="{}"),
        sa.Column("status", sa.String(20), default="pending", index=True),
        sa.Column("error", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Forward-only — downgrade ЗАПРЕЩЁН."""
    raise NotImplementedError(
        "Forward-only: rollback through new migration + rebuild. "
        "See recovery playbook."
    )
