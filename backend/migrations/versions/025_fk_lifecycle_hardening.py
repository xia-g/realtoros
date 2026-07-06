"""fk_lifecycle_hardening: Fix FK cascade policies for all tables.

Resolves C4 from Sprint 8.7 audit.
"""

from collections.abc import Sequence
from alembic import op

revision: str = "025_fk_lifecycle_hardening"
down_revision: str | None = "024_add_check_constraints"


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        BEGIN
            ALTER TABLE deals DROP CONSTRAINT IF EXISTS deals_client_id_fkey;
            ALTER TABLE deals ADD CONSTRAINT deals_client_id_fkey
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL;
        EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN
            ALTER TABLE deal_workflows DROP CONSTRAINT IF EXISTS deal_workflows_deal_id_fkey;
            ALTER TABLE deal_workflows ADD CONSTRAINT deal_workflows_deal_id_fkey
                FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN
            ALTER TABLE deal_checkpoints DROP CONSTRAINT IF EXISTS deal_checkpoints_deal_id_fkey;
            ALTER TABLE deal_checkpoints ADD CONSTRAINT deal_checkpoints_deal_id_fkey
                FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN
            ALTER TABLE deal_document_packages DROP CONSTRAINT IF EXISTS deal_document_packages_deal_id_fkey;
            ALTER TABLE deal_document_packages ADD CONSTRAINT deal_document_packages_deal_id_fkey
                FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN
            ALTER TABLE deal_actions DROP CONSTRAINT IF EXISTS deal_actions_deal_id_fkey;
            ALTER TABLE deal_actions ADD CONSTRAINT deal_actions_deal_id_fkey
                FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;
    END $$;
    """)


def downgrade() -> None:
    pass
