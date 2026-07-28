"""Add updated_at column to graph_nodes.

The column existed in the ORM model (backend/models/graph_node.py)
but was never added to the database table.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: str | None = "037_add_property_cadastral_number"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "graph_nodes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("graph_nodes", "updated_at")
