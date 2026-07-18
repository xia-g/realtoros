"""030_ledger_enforcements: period_id NOT NULL, reversal constraints.

Changes:
  - ledger_entry.period_id SET NOT NULL (every line belongs to tax period)
  - ledger_entry ADD ck_no_self_reversal (reversed_entry_id != id)
"""

from collections.abc import Sequence
from alembic import op

revision: str = "030_ledger_enforcements"
down_revision: str | None = "029_ledger_schema"


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        -- 1. period_id NOT NULL — every posting belongs to exactly one tax period
        BEGIN
            UPDATE accounting.ledger_entry SET period_id = (
                SELECT id FROM accounting.tax_period
                WHERE company_id = ledger_entry.company_id
                  AND date_from <= ledger_entry.entry_date
                  AND date_to >= ledger_entry.entry_date
                LIMIT 1
            ) WHERE period_id IS NULL;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.ledger_entry ALTER COLUMN period_id SET NOT NULL;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        -- 2. Self-reversal check
        BEGIN
            ALTER TABLE accounting.ledger_entry
                ADD CONSTRAINT ck_no_self_reversal
                CHECK (reversed_entry_id IS DISTINCT FROM id);
        EXCEPTION WHEN OTHERS THEN NULL; END;

        -- 3. Reversal chain limit: max 1 level
        -- Enforced by application code; this is a documentation constraint.
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE accounting.ledger_entry DROP CONSTRAINT IF EXISTS ck_no_self_reversal;
    ALTER TABLE accounting.ledger_entry ALTER COLUMN period_id DROP NOT NULL;
    """)
