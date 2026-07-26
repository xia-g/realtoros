"""Add deal_id, source_event_id, source_type to accounting_documents and journal_entries.

BRIDGE-1: Established deal → accounting correlation.
Allows traceability from deal events to accounting documents and journal entries.

Tables:
  - accounting_documents: add deal_id, source_event_id, source_type
  - journal_entries: add source_event_id, source_type
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "038_add_accounting_correlation"
down_revision: str | None = "037_add_property_cadastral_number"


def upgrade() -> None:
    # ── accounting_documents (managed by accounting_binding) ─────────
    op.add_column(
        "accounting_documents",
        sa.Column("deal_id", sa.String(36), nullable=True, index=True),
    )
    op.add_column(
        "accounting_documents",
        sa.Column("source_event_id", sa.String(36), nullable=True, index=True),
    )
    op.add_column(
        "accounting_documents",
        sa.Column("source_type", sa.String(64), nullable=True, index=True),
    )

    # ── journal_entries (managed by accounting_binding) ──────────
    op.add_column(
        "journal_entries",
        sa.Column("source_event_id", sa.String(36), nullable=True, index=True),
    )
    op.add_column(
        "journal_entries",
        sa.Column("source_type", sa.String(64), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("accounting_documents", "deal_id")
    op.drop_column("accounting_documents", "source_event_id")
    op.drop_column("accounting_documents", "source_type")
    op.drop_column("journal_entries", "source_event_id")
    op.drop_column("journal_entries", "source_type")
