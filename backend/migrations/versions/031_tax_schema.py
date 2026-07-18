"""031_tax_schema: Create tax layer tables for Phase 4.

New tables (accounting schema):
  - tax_policy                    (immutable tax policy catalog)
  - tax_policy_version            (versioned policy snapshots)
  - tax_rule                      (individual rules within a policy)
  - tax_assignment                (ledger_line → tax register mapping)
  - tax_register                  (immutable register per period + type)
  - tax_register_entry            (individual entries within register)
  - tax_explanation               (explainability chain)

Invariants:
  - One ledger_line → exactly ONE active (is_current=true) assignment
  - Tax register is immutable (INSERT only, no UPDATE/DELETE)
  - Replay creates new assignments (old superseded via is_current=false)
  - Tax = f(Ledger, TaxPolicyVersion) — NOT LedgerLine.tax_register_id
"""

from collections.abc import Sequence

from alembic import op

revision: str = "031_tax_schema"
down_revision: str | None = "030_ledger_enforcements"


def upgrade() -> None:
    # ── tax_policy ─────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_policy (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        name            VARCHAR(100)    NOT NULL,
        description     TEXT            NULL,
        tax_regime      VARCHAR(20)     NOT NULL,
        is_active       BOOLEAN         NOT NULL DEFAULT true,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_policy PRIMARY KEY (id),
        CONSTRAINT uq_tax_policy_name UNIQUE (name),
        CONSTRAINT ck_tax_policy_regime CHECK (
            tax_regime IN ('USN_D', 'USN_DR', 'GENERAL', 'PATENT')
        )
    );
    """)

    # ── tax_policy_version ─────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_policy_version (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        policy_id       UUID            NOT NULL,
        version         VARCHAR(30)     NOT NULL,
        effective_from  DATE            NOT NULL,
        effective_to    DATE            NULL,
        rules_hash      VARCHAR(64)     NOT NULL,
        is_active       BOOLEAN         NOT NULL DEFAULT true,
        metadata_json   JSONB           NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_policy_version PRIMARY KEY (id),
        CONSTRAINT uq_policy_version UNIQUE (policy_id, version),
        CONSTRAINT fk_tpv_policy FOREIGN KEY (policy_id)
            REFERENCES accounting.tax_policy(id) ON DELETE CASCADE,
        CONSTRAINT ck_tpv_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
    );
    """)

    # ── tax_rule ────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_rule (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        policy_version_id   UUID            NOT NULL,
        priority            INTEGER         NOT NULL DEFAULT 0,
        rule_code           VARCHAR(50)     NOT NULL,
        account_pattern     VARCHAR(20)     NULL,
        direction           VARCHAR(10)     NULL,
        register_type       VARCHAR(20)     NOT NULL,
        tax_treatment       VARCHAR(20)     NOT NULL,
        excluded            BOOLEAN         NOT NULL DEFAULT false,
        reason_code         VARCHAR(30)     NULL,
        amount_multiplier   NUMERIC(10,6)   NOT NULL DEFAULT 1.0,
        metadata_json       JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_rule PRIMARY KEY (id),
        CONSTRAINT fk_tax_rule_version FOREIGN KEY (policy_version_id)
            REFERENCES accounting.tax_policy_version(id) ON DELETE CASCADE,
        CONSTRAINT ck_tax_rule_register CHECK (
            register_type IN (
                'KUDIR_INCOME', 'KUDIR_EXPENSE',
                'VAT_SALES', 'VAT_PURCHASE',
                'GENERAL_INCOME', 'GENERAL_EXPENSE',
                'EXCLUDED'
            )
        ),
        CONSTRAINT ck_tax_rule_treatment CHECK (
            tax_treatment IN ('taxable', 'deductible', 'exempt', 'excluded')
        ),
        CONSTRAINT ck_tax_rule_direction CHECK (
            direction IS NULL OR direction IN ('debit', 'credit')
        ),
        CONSTRAINT ck_tax_rule_reason CHECK (
            reason_code IS NULL OR reason_code IN (
                'balance_account', 'unmapped_account',
                'internal_transfer', 'vat_reclaim',
                'non_taxable_income', 'non_deductible_expense',
                'manual_exclusion', 'no_active_policy'
            )
        )
    );
    """)

    # ── tax_assignment ──────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_assignment (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        ledger_line_id      UUID            NOT NULL,
        ledger_entry_id     UUID            NOT NULL,
        company_id          UUID            NOT NULL,
        policy_version_id   UUID            NOT NULL,
        tax_rule_id         UUID            NULL,
        register_type       VARCHAR(20)     NOT NULL,
        tax_treatment       VARCHAR(20)     NOT NULL,
        excluded            BOOLEAN         NOT NULL DEFAULT false,
        reason_code         VARCHAR(30)     NULL,
        is_current          BOOLEAN         NOT NULL DEFAULT true,
        superseded_by       UUID            NULL,
        version             INTEGER         NOT NULL DEFAULT 1,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_assignment PRIMARY KEY (id),
        CONSTRAINT fk_tax_assignment_line FOREIGN KEY (ledger_line_id)
            REFERENCES accounting.ledger_line(id) ON DELETE CASCADE,
        CONSTRAINT fk_tax_assignment_entry FOREIGN KEY (ledger_entry_id)
            REFERENCES accounting.ledger_entry(id) ON DELETE CASCADE,
        CONSTRAINT fk_tax_assignment_policy FOREIGN KEY (policy_version_id)
            REFERENCES accounting.tax_policy_version(id) ON DELETE RESTRICT,
        CONSTRAINT fk_tax_assignment_rule FOREIGN KEY (tax_rule_id)
            REFERENCES accounting.tax_rule(id) ON DELETE SET NULL,
        CONSTRAINT ck_tax_assignment_register CHECK (
            register_type IN (
                'KUDIR_INCOME', 'KUDIR_EXPENSE',
                'VAT_SALES', 'VAT_PURCHASE',
                'GENERAL_INCOME', 'GENERAL_EXPENSE',
                'EXCLUDED'
            )
        ),
        CONSTRAINT ck_tax_assignment_treatment CHECK (
            tax_treatment IN ('taxable', 'deductible', 'exempt', 'excluded')
        ),
        CONSTRAINT ck_tax_assignment_reason CHECK (
            reason_code IS NULL OR reason_code IN (
                'balance_account', 'unmapped_account',
                'internal_transfer', 'vat_reclaim',
                'non_taxable_income', 'non_deductible_expense',
                'manual_exclusion', 'no_active_policy'
            )
        )
    );
    """)

    # ── tax_register ────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_register (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        company_id          UUID            NOT NULL,
        tax_period_id       UUID            NOT NULL,
        register_type       VARCHAR(20)     NOT NULL,
        register_version    INTEGER         NOT NULL DEFAULT 1,
        policy_version_id   UUID            NOT NULL,
        entry_count         INTEGER         NOT NULL DEFAULT 0,
        total_amount        NUMERIC(20,2)   NOT NULL DEFAULT 0,
        is_current          BOOLEAN         NOT NULL DEFAULT true,
        metadata_json       JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_register PRIMARY KEY (id),
        CONSTRAINT fk_tax_reg_policy FOREIGN KEY (policy_version_id)
            REFERENCES accounting.tax_policy_version(id) ON DELETE RESTRICT,
        CONSTRAINT fk_tax_reg_period FOREIGN KEY (tax_period_id)
            REFERENCES accounting.tax_period(id) ON DELETE RESTRICT,
        CONSTRAINT ck_tax_register_type CHECK (
            register_type IN (
                'KUDIR_INCOME', 'KUDIR_EXPENSE',
                'VAT_SALES', 'VAT_PURCHASE',
                'GENERAL_INCOME', 'GENERAL_EXPENSE',
                'EXCLUDED'
            )
        ),
        CONSTRAINT uq_tax_register_version UNIQUE (company_id, tax_period_id, register_type, register_version)
    );
    """)

    # ── tax_register_entry ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_register_entry (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        register_id         UUID            NOT NULL,
        assignment_id       UUID            NOT NULL,
        ledger_line_id      UUID            NOT NULL,
        account_code        VARCHAR(20)     NOT NULL,
        amount              NUMERIC(16,2)   NOT NULL,
        direction           VARCHAR(10)     NOT NULL,
        tax_treatment       VARCHAR(20)     NOT NULL,
        excluded            BOOLEAN         NOT NULL DEFAULT false,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_register_entry PRIMARY KEY (id),
        CONSTRAINT fk_tax_reg_entry_register FOREIGN KEY (register_id)
            REFERENCES accounting.tax_register(id) ON DELETE CASCADE,
        CONSTRAINT fk_tax_reg_entry_assignment FOREIGN KEY (assignment_id)
            REFERENCES accounting.tax_assignment(id) ON DELETE RESTRICT,
        CONSTRAINT fk_tax_reg_entry_line FOREIGN KEY (ledger_line_id)
            REFERENCES accounting.ledger_line(id) ON DELETE RESTRICT,
        CONSTRAINT ck_tax_reg_entry_direction CHECK (direction IN ('debit', 'credit'))
    );
    """)

    # ── tax_explanation ─────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_explanation (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        register_entry_id   UUID            NOT NULL,
        assignment_id       UUID            NOT NULL,
        ledger_line_id      UUID            NOT NULL,
        ledger_entry_id     UUID            NOT NULL,
        posting_decision_link_id UUID      NULL,
        decision_id         UUID            NULL,
        decision_explanation_id UUID     NULL,
        register_type       VARCHAR(20)     NOT NULL,
        tax_treatment       VARCHAR(20)     NOT NULL,
        excluded            BOOLEAN         NOT NULL DEFAULT false,
        reason_code         VARCHAR(30)     NULL,
        why_included        TEXT            NULL,
        why_excluded        TEXT            NULL,
        rule_code           VARCHAR(50)     NULL,
        chain_json          JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_explanation PRIMARY KEY (id),
        CONSTRAINT fk_tax_expl_reg_entry FOREIGN KEY (register_entry_id)
            REFERENCES accounting.tax_register_entry(id) ON DELETE CASCADE,
        CONSTRAINT fk_tax_expl_assignment FOREIGN KEY (assignment_id)
            REFERENCES accounting.tax_assignment(id) ON DELETE RESTRICT
    );
    """)

    # ── Foreign Keys (additional) ───────────────────────────────────
    op.execute("""
    DO $$ BEGIN
        BEGIN
            ALTER TABLE accounting.tax_assignment
                ADD CONSTRAINT fk_tax_assignment_superseded
                FOREIGN KEY (superseded_by) REFERENCES accounting.tax_assignment(id) ON DELETE SET NULL;
        EXCEPTION WHEN OTHERS THEN NULL; END;
    END $$;
    """)

    # ── Indexes ─────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_assignment_line ON accounting.tax_assignment(ledger_line_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_assignment_current ON accounting.tax_assignment(ledger_line_id, is_current) WHERE is_current = true;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_assignment_company ON accounting.tax_assignment(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_assignment_policy ON accounting.tax_assignment(policy_version_id);")

    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_register_company ON accounting.tax_register(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_register_period ON accounting.tax_register(tax_period_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_register_current ON accounting.tax_register(company_id, tax_period_id, register_type) WHERE is_current = true;")

    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_reg_entry_register ON accounting.tax_register_entry(register_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_reg_entry_assignment ON accounting.tax_register_entry(assignment_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_reg_entry_line ON accounting.tax_register_entry(ledger_line_id);")

    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_expl_reg_entry ON accounting.tax_explanation(register_entry_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_expl_assignment ON accounting.tax_explanation(assignment_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_expl_decision ON accounting.tax_explanation(decision_id);")

    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_policy_active ON accounting.tax_policy(is_active) WHERE is_active = true;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_policy_version_active ON accounting.tax_policy_version(policy_id, is_active) WHERE is_active = true;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tax_rule_version ON accounting.tax_rule(policy_version_id);")


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.tax_explanation CASCADE;
    DROP TABLE IF EXISTS accounting.tax_register_entry CASCADE;
    DROP TABLE IF EXISTS accounting.tax_register CASCADE;
    DROP TABLE IF EXISTS accounting.tax_assignment CASCADE;
    DROP TABLE IF EXISTS accounting.tax_rule CASCADE;
    DROP TABLE IF EXISTS accounting.tax_policy_version CASCADE;
    DROP TABLE IF EXISTS accounting.tax_policy CASCADE;
    """)
