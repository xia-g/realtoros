"""Add promoted_deal_id column to document_intake for Deal correlation.

Part of Epic 3 Product Layer Alignment:
- Document -> Deal bridge via promoted_deal_id
- Canonical identity: document_intake.document_id -> document_intake.promoted_deal_id -> deals.id
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "040_add_promoted_deal_id"
down_revision: Union[str, Sequence[str], None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_intake",
        sa.Column("promoted_deal_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "idx_document_intake_promoted_deal",
        "document_intake",
        ["promoted_deal_id"],
        postgresql_where=sa.text("promoted_deal_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_document_intake_promoted_deal")
    op.drop_column("document_intake", "promoted_deal_id")
