"""Add inn column to clients table with partial unique index.

INN (ИНН) — the definitive business identifier for Russian parties.
ADR-002: nullable VARCHAR(12) + partial unique index WHERE inn IS NOT NULL.
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "036_add_client_inn"
down_revision: str | None = "035_event_backbone_tables"


def upgrade() -> None:
    op.add_column("clients", sa.Column("inn", sa.String(12), nullable=True))
    op.create_index(
        "idx_clients_inn_unique",
        "clients",
        ["inn"],
        unique=True,
        postgresql_where=sa.text("inn IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_clients_inn_unique")
    op.drop_column("clients", "inn")
