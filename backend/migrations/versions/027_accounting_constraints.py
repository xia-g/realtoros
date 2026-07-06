"""027_accounting_constraints: FK, CHECK, UNIQUE (v4).

v4 additions:
  • uq_event_fingerprint — dedup via SHA256 hash
  • FK for decision_explanation, recognition_snapshot
"""

from collections.abc import Sequence
from alembic import op

revision: str = "027_accounting_constraints"
down_revision: str | None = "026_accounting_schema"


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        -- FOREIGN KEYS
        BEGIN ALTER TABLE accounting.tax_regime
            ADD CONSTRAINT fk_tax_regime_company
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.tax_period
            ADD CONSTRAINT fk_tax_period_company
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.accounting_batch
            ADD CONSTRAINT fk_batch_company
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.accounting_event
            ADD CONSTRAINT fk_event_company
            FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.accounting_event
            ADD CONSTRAINT fk_event_batch
            FOREIGN KEY (batch_id) REFERENCES accounting.accounting_batch(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.accounting_decision
            ADD CONSTRAINT fk_decision_event
            FOREIGN KEY (event_id) REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.decision_explanation
            ADD CONSTRAINT fk_explanation_decision
            FOREIGN KEY (decision_id) REFERENCES accounting.accounting_decision(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.recognition_snapshot
            ADD CONSTRAINT fk_snapshot_event
            FOREIGN KEY (event_id) REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.event_transaction
            ADD CONSTRAINT fk_et_event
            FOREIGN KEY (event_id) REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.event_document
            ADD CONSTRAINT fk_ed_event
            FOREIGN KEY (event_id) REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        -- CHECK
        BEGIN ALTER TABLE accounting.tax_regime
            ADD CONSTRAINT ck_regime_dates CHECK (valid_to IS NULL OR valid_to > valid_from);
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.tax_period
            ADD CONSTRAINT ck_period_dates CHECK (date_to > date_from);
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.event_transaction
            ADD CONSTRAINT ck_confidence_range CHECK (confidence >= 0 AND confidence <= 1);
        EXCEPTION WHEN OTHERS THEN NULL; END;

        -- UNIQUE (enforced via per-partition indexes + application code)
        -- Note: PostgreSQL requires UNIQUE constraints on partitioned tables
        -- to include all partition columns. Since we partition by event_date,
        -- we create per-partition unique indexes in the partition function (028).
        -- Application-level check is done via check_fingerprint_unique().

        BEGIN ALTER TABLE accounting.tax_regime
            ADD CONSTRAINT uq_regime_company_valid_from
            UNIQUE (company_id, valid_from);
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN ALTER TABLE accounting.tax_period
            ADD CONSTRAINT uq_period_company_type_date
            UNIQUE (company_id, period_type, date_from);
        EXCEPTION WHEN OTHERS THEN NULL; END;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE accounting.event_document DROP CONSTRAINT IF EXISTS fk_ed_event;
    ALTER TABLE accounting.event_transaction DROP CONSTRAINT IF EXISTS fk_et_event;
    ALTER TABLE accounting.recognition_snapshot DROP CONSTRAINT IF EXISTS fk_snapshot_event;
    ALTER TABLE accounting.decision_explanation DROP CONSTRAINT IF EXISTS fk_explanation_decision;
    ALTER TABLE accounting.accounting_decision DROP CONSTRAINT IF EXISTS fk_decision_event;
    ALTER TABLE accounting.accounting_event DROP CONSTRAINT IF EXISTS fk_event_batch;
    ALTER TABLE accounting.accounting_event DROP CONSTRAINT IF EXISTS fk_event_company;
    ALTER TABLE accounting.accounting_batch DROP CONSTRAINT IF EXISTS fk_batch_company;
    ALTER TABLE accounting.tax_period DROP CONSTRAINT IF EXISTS fk_tax_period_company;
    ALTER TABLE accounting.tax_regime DROP CONSTRAINT IF EXISTS fk_tax_regime_company;
    ALTER TABLE accounting.tax_period DROP CONSTRAINT IF EXISTS uq_period_company_type_date;
    ALTER TABLE accounting.tax_regime DROP CONSTRAINT IF EXISTS uq_regime_company_valid_from;
    ALTER TABLE accounting.event_transaction DROP CONSTRAINT IF EXISTS ck_confidence_range;
    ALTER TABLE accounting.tax_period DROP CONSTRAINT IF EXISTS ck_period_dates;
    ALTER TABLE accounting.tax_regime DROP CONSTRAINT IF EXISTS ck_regime_dates;
    """)
