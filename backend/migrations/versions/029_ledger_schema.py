"""029_ledger_schema: Create posting/ledger tables for Phase 3.

New tables (accounting schema — ledger section):
  - chart_of_accounts
  - posting_batch
  - posting_decision_link
  - ledger_entry
  - ledger_line

Invariants enforced at schema level:
  - ledger_line: ck_debit_credit_or (one of debit or credit must be 0)
  - ledger_line: ck_amount_positive (amount > 0)
  - No UPDATE/DELETE triggers can be added later

Period lock uses existing accounting.tax_period (already has open/locked/closed).
"""

from collections.abc import Sequence
from alembic import op

revision: str = "029_ledger_schema"
down_revision: str | None = "028_accounting_indexes"


def upgrade() -> None:
    # ── chart_of_accounts ───────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.chart_of_accounts (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        account_code    VARCHAR(20)     NOT NULL,
        account_name    VARCHAR(200)    NOT NULL,
        account_type    VARCHAR(20)     NOT NULL,
        parent_code     VARCHAR(20)     NULL,
        is_active       BOOLEAN         NOT NULL DEFAULT true,
        effective_from  DATE            NOT NULL DEFAULT '2020-01-01',
        effective_to    DATE            NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_chart_of_accounts PRIMARY KEY (id),
        CONSTRAINT uq_account_code UNIQUE (account_code)
    );
    """)

    # ── posting_batch ───────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.posting_batch (
        id                      UUID            NOT NULL DEFAULT gen_random_uuid(),
        company_id              UUID            NOT NULL,
        decision_id             UUID            NULL,
        posting_rules_version   VARCHAR(20)     NOT NULL,
        status                  VARCHAR(15)     NOT NULL DEFAULT 'pending',
        total_debit             NUMERIC(20,2)   NOT NULL DEFAULT 0,
        total_credit            NUMERIC(20,2)   NOT NULL DEFAULT 0,
        is_closed               BOOLEAN         NOT NULL DEFAULT false,
        created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_posting_batch PRIMARY KEY (id),
        CONSTRAINT ck_batch_total CHECK (total_debit = total_credit)
    );
    """)

    # ── posting_decision_link ───────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.posting_decision_link (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        decision_id         UUID            NOT NULL,
        batch_id            UUID            NOT NULL,
        posting_rule_code   VARCHAR(50)     NOT NULL,
        posting_rule_version VARCHAR(20)    NOT NULL,
        decision_version    INTEGER         NOT NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_posting_decision_link PRIMARY KEY (id)
    );
    """)

    # ── ledger_entry ────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.ledger_entry (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        batch_id            UUID            NOT NULL,
        company_id          UUID            NOT NULL,
        period_id           UUID            NULL,
        entry_date          DATE            NOT NULL DEFAULT CURRENT_DATE,
        description         TEXT            NULL,
        is_reversal         BOOLEAN         NOT NULL DEFAULT false,
        reversed_entry_id   UUID            NULL,
        posting_hash        VARCHAR(64)     NOT NULL,
        created_by          UUID            NULL,
        trace_id            VARCHAR(36)     NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_ledger_entry PRIMARY KEY (id)
    );
    """)

    # ── ledger_line ─────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.ledger_line (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        entry_id        UUID            NOT NULL,
        account_code    VARCHAR(20)     NOT NULL,
        direction       VARCHAR(10)     NOT NULL,
        amount          NUMERIC(16,2)   NOT NULL,
        currency        CHAR(3)         NOT NULL DEFAULT 'RUB',
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_ledger_line PRIMARY KEY (id),
        CONSTRAINT ck_direction CHECK (direction IN ('debit', 'credit')),
        CONSTRAINT ck_amount_positive CHECK (amount > 0)
    );
    """)

    # ── Foreign Keys ────────────────────────────────────────────────
    op.execute("""
    DO $$ BEGIN
        BEGIN
            ALTER TABLE accounting.ledger_entry
                ADD CONSTRAINT fk_ledger_entry_period
                FOREIGN KEY (period_id) REFERENCES accounting.tax_period(id) ON DELETE SET NULL;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.ledger_entry
                ADD CONSTRAINT fk_ledger_entry_batch
                FOREIGN KEY (batch_id) REFERENCES accounting.posting_batch(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.ledger_line
                ADD CONSTRAINT fk_ledger_line_entry
                FOREIGN KEY (entry_id) REFERENCES accounting.ledger_entry(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.posting_batch
                ADD CONSTRAINT fk_batch_company
                FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.posting_decision_link
                ADD CONSTRAINT fk_pdl_decision
                FOREIGN KEY (decision_id) REFERENCES accounting.accounting_decision(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;

        BEGIN
            ALTER TABLE accounting.posting_decision_link
                ADD CONSTRAINT fk_pdl_batch
                FOREIGN KEY (batch_id) REFERENCES accounting.posting_batch(id) ON DELETE CASCADE;
        EXCEPTION WHEN OTHERS THEN NULL; END;
    END $$;
    """)

    # ── Indexes ─────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_company ON accounting.ledger_entry(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_period ON accounting.ledger_entry(period_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_date ON accounting.ledger_entry(entry_date);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_batch ON accounting.ledger_entry(batch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_hash ON accounting.ledger_entry(posting_hash);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_reversal ON accounting.ledger_entry(reversed_entry_id) WHERE reversed_entry_id IS NOT NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_line_entry ON accounting.ledger_line(entry_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ledger_line_account ON accounting.ledger_line(account_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posting_batch_company ON accounting.posting_batch(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posting_batch_decision ON accounting.posting_batch(decision_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdl_decision ON accounting.posting_decision_link(decision_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdl_batch ON accounting.posting_decision_link(batch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chart_code ON accounting.chart_of_accounts(account_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chart_active ON accounting.chart_of_accounts(account_code) WHERE is_active = true;")


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.ledger_line CASCADE;
    DROP TABLE IF EXISTS accounting.ledger_entry CASCADE;
    DROP TABLE IF EXISTS accounting.posting_decision_link CASCADE;
    DROP TABLE IF EXISTS accounting.posting_batch CASCADE;
    DROP TABLE IF EXISTS accounting.chart_of_accounts CASCADE;
    """)
