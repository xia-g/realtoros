"""028_accounting_indexes: Performance indexes + partition function (v4).

v4 additions:
  • idx_event_processing — queue worker (new/recognizing/deciding/failed)
  • idx_explanation_decision, idx_explanation_rule — decision detail lookup
  • idx_snapshot_event — snapshot by event
"""

from collections.abc import Sequence
from alembic import op

revision: str = "028_accounting_indexes"
down_revision: str | None = "027_accounting_constraints"


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        -- tax_regime
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tax_regime_company') THEN
            CREATE INDEX idx_tax_regime_company ON accounting.tax_regime(company_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tax_regime_valid_from') THEN
            CREATE INDEX idx_tax_regime_valid_from ON accounting.tax_regime(valid_from);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tax_regime_active') THEN
            CREATE INDEX idx_tax_regime_active ON accounting.tax_regime(company_id, is_active) WHERE is_active = true;
        END IF;

        -- tax_period
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tax_period_company') THEN
            CREATE INDEX idx_tax_period_company ON accounting.tax_period(company_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tax_period_open') THEN
            CREATE INDEX idx_tax_period_open ON accounting.tax_period(company_id, status) WHERE status = 'open';
        END IF;

        -- accounting_batch
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_batch_company') THEN
            CREATE INDEX idx_batch_company ON accounting.accounting_batch(company_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_batch_status') THEN
            CREATE INDEX idx_batch_status ON accounting.accounting_batch(status);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_batch_external_key') THEN
            CREATE INDEX idx_batch_external_key ON accounting.accounting_batch(external_batch_key)
                WHERE external_batch_key IS NOT NULL;
        END IF;

        -- accounting_event
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_company') THEN
            CREATE INDEX idx_event_company ON accounting.accounting_event(company_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_date') THEN
            CREATE INDEX idx_event_date ON accounting.accounting_event(event_date);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_source') THEN
            CREATE INDEX idx_event_source ON accounting.accounting_event(source_system, source_type, source_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_status') THEN
            CREATE INDEX idx_event_status ON accounting.accounting_event(recognition_status);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_current') THEN
            CREATE INDEX idx_event_current ON accounting.accounting_event(company_id, is_current) WHERE is_current = true;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_company_date') THEN
            CREATE INDEX idx_event_company_date ON accounting.accounting_event(company_id, event_date DESC);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_decision_state') THEN
            CREATE INDEX idx_event_decision_state ON accounting.accounting_event(company_id, decision_state);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_event_processing') THEN
            CREATE INDEX idx_event_processing ON accounting.accounting_event(processing_state, next_retry_at)
                WHERE processing_state IN ('new','recognizing','ready_for_decision','deciding','failed');
        END IF;

        -- accounting_decision
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_decision_event') THEN
            CREATE INDEX idx_decision_event ON accounting.accounting_decision(event_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_decision_included') THEN
            CREATE INDEX idx_decision_included ON accounting.accounting_decision(included);
        END IF;

        -- decision_explanation
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_explanation_decision') THEN
            CREATE INDEX idx_explanation_decision ON accounting.decision_explanation(decision_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_explanation_rule') THEN
            CREATE INDEX idx_explanation_rule ON accounting.decision_explanation(rule_code);
        END IF;

        -- recognition_snapshot
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_snapshot_event') THEN
            CREATE INDEX idx_snapshot_event ON accounting.recognition_snapshot(event_id);
        END IF;

        -- link tables
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_et_transaction') THEN
            CREATE INDEX idx_et_transaction ON accounting.event_transaction(transaction_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_ed_document') THEN
            CREATE INDEX idx_ed_document ON accounting.event_document(document_id);
        END IF;
    END $$;
    """)

    # ── Partition function ─────────────────────────────────────────
    op.execute("""
    CREATE OR REPLACE FUNCTION accounting.create_monthly_partition(p_month DATE DEFAULT date_trunc('month', CURRENT_DATE)::DATE)
    RETURNS VOID AS $$
    DECLARE
        v_part_name TEXT; v_from DATE; v_to DATE;
    BEGIN
        v_from := date_trunc('month', p_month)::DATE;
        v_to   := (v_from + INTERVAL '1 month')::DATE;
        v_part_name := 'accounting_event_' || to_char(v_from, 'YYYY_MM');
        IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = v_part_name) THEN
            EXECUTE format('CREATE TABLE accounting.%I PARTITION OF accounting.accounting_event FOR VALUES FROM (%L) TO (%L)', v_part_name, v_from, v_to);
            -- Per-partition unique dedup indexes
            EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS uq_event_fingerprint_%s ON accounting.%I(company_id, event_fingerprint, is_current) WHERE is_current = true', to_char(v_from, 'YYYY_MM'), v_part_name);
            EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS uq_event_source_active_%s ON accounting.%I(source_system, source_type, source_id, event_type, is_current) WHERE is_current = true', to_char(v_from, 'YYYY_MM'), v_part_name);
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("SELECT accounting.create_monthly_partition();")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS accounting.create_monthly_partition();")
    op.execute("""
    DROP INDEX IF EXISTS accounting.idx_ed_document;
    DROP INDEX IF EXISTS accounting.idx_et_transaction;
    DROP INDEX IF EXISTS accounting.idx_snapshot_event;
    DROP INDEX IF EXISTS accounting.idx_explanation_rule;
    DROP INDEX IF EXISTS accounting.idx_explanation_decision;
    DROP INDEX IF EXISTS accounting.idx_decision_included;
    DROP INDEX IF EXISTS accounting.idx_decision_event;
    DROP INDEX IF EXISTS accounting.idx_event_processing;
    DROP INDEX IF EXISTS accounting.idx_event_decision_state;
    DROP INDEX IF EXISTS accounting.idx_event_company_date;
    DROP INDEX IF EXISTS accounting.idx_event_current;
    DROP INDEX IF EXISTS accounting.idx_event_status;
    DROP INDEX IF EXISTS accounting.idx_event_source;
    DROP INDEX IF EXISTS accounting.idx_event_date;
    DROP INDEX IF EXISTS accounting.idx_event_company;
    DROP INDEX IF EXISTS accounting.idx_batch_external_key;
    DROP INDEX IF EXISTS accounting.idx_batch_status;
    DROP INDEX IF EXISTS accounting.idx_batch_company;
    DROP INDEX IF EXISTS accounting.idx_tax_period_open;
    DROP INDEX IF EXISTS accounting.idx_tax_period_company;
    DROP INDEX IF EXISTS accounting.idx_tax_regime_active;
    DROP INDEX IF EXISTS accounting.idx_tax_regime_valid_from;
    DROP INDEX IF EXISTS accounting.idx_tax_regime_company;
    """)
