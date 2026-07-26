"""Add cadastral_number column to properties table with partial unique index.

Cadastral number (кадастровый номер) — the definitive Russian property identifier.
ADR-003: nullable VARCHAR(50) + partial unique index WHERE cadastral_number IS NOT NULL.
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "037_add_property_cadastral_number"
down_revision: str | None = "036_add_client_inn"


def upgrade() -> None:
    op.add_column(
        "properties", sa.Column("cadastral_number", sa.String(50), nullable=True)
    )
    op.create_index(
        "idx_properties_cadastral_unique",
        "properties",
        ["cadastral_number"],
        unique=True,
        postgresql_where=sa.text("cadastral_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_properties_cadastral_unique")
    op.drop_column("properties", "cadastral_number")
