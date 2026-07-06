"""033_reconciliation_schema: Create reconciliation layer tables for Phase 6.

New tables (accounting schema):
  - reconciliation_run           (immutable snapshot of comparison state)
  - reconciliation_item          (individual items being compared)
  - reconciliation_match         (matched pairs between systems)
  - reconciliation_gap           (detected discrepancies)
  - reconciliation_explanation   (explainability for gaps/matches)

Invariants:
  - Reconciliation = f(Ledger, BankData, ExternalData, Snapshots)
  - Append-only: reconciliation runs never mutate
  - Same inputs → same matches → same gaps (deterministic)
  - Reconciliation does NOT change ledger, bank data, or tax registers
"""

from collections.abc import Sequence

from alembic import op

revision: str = "033_reconciliation_schema"
down_revision: str | None = "032_reporting_schema"


def upgrade() -> None:
    # ── reconciliation_run ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.reconciliation_run (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        company_id      UUID            NOT NULL,
        run_version     INTEGER         NOT NULL DEFAULT 1,
        status          VARCHAR(15)     NOT NULL DEFAULT 'open',
        source_systems  JSONB           NOT NULL DEFAULT '[]',
        period_from     DATE            NULL,
        period_to       DATE            NULL,
        ledger_entries_count INTEGER   NOT NULL DEFAULT 0,
        bank_entries_count  INTEGER   NOT NULL DEFAULT 0,
        matches_count   INTEGER         NOT NULL DEFAULT 0,
        gaps_count      INTEGER         NOT NULL DEFAULT 0,
        run_hash        VARCHAR(64)     NOT NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        closed_at       TIMESTAMPTZ     NULL,
        metadata_json   JSONB           NULL,
        CONSTRAINT pk_reconciliation_run PRIMARY KEY (id),
        CONSTRAINT ck_rec_run_status CHECK (
            status IN ('open', 'in_progress', 'matched_partial',
                       'matched_full', 'unresolved', 'closed')
        )
    );
    """)

    # ── reconciliation_item ─────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.reconciliation_item (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        run_id          UUID            NOT NULL,
        system          VARCHAR(30)     NOT NULL,
        external_id     VARCHAR(100)    NOT NULL,
        item_type       VARCHAR(30)     NOT NULL,
        amount          NUMERIC(16,2)   NOT NULL,
        currency        CHAR(3)         NOT NULL DEFAULT 'RUB',
        direction       VARCHAR(10)     NULL,
        item_date       DATE            NULL,
        description     TEXT            NULL,
        checksum        VARCHAR(64)     NULL,
        metadata_json   JSONB           NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_reconciliation_item PRIMARY KEY (id),
        CONSTRAINT fk_ri_run FOREIGN KEY (run_id)
            REFERENCES accounting.reconciliation_run(id) ON DELETE CASCADE,
        CONSTRAINT ck_ri_system CHECK (
            system IN ('ledger', 'bank', 'erp', 'payment_processor', 'crm', 'external')
        ),
        CONSTRAINT ck_ri_type CHECK (
            item_type IN ('posting', 'bank_transaction', 'tax_register',
                          'source_event', 'invoice', 'payment', 'other')
        ),
        CONSTRAINT ck_ri_direction CHECK (
            direction IS NULL OR direction IN ('inflow', 'outflow', 'debit', 'credit')
        )
    );
    """)

    # ── reconciliation_match ────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.reconciliation_match (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        run_id              UUID            NOT NULL,
        match_type          VARCHAR(15)     NOT NULL,
        confidence_score    NUMERIC(5,4)    NOT NULL DEFAULT 1.0,
        amount_delta        NUMERIC(16,2)   NOT NULL DEFAULT 0,
        date_delta_days     INTEGER         NOT NULL DEFAULT 0,
        source_item_id      UUID            NOT NULL,
        target_item_id      UUID            NOT NULL,
        matching_rule       VARCHAR(50)     NOT NULL,
        matched_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        metadata_json       JSONB           NULL,
        CONSTRAINT pk_reconciliation_match PRIMARY KEY (id),
        CONSTRAINT fk_rm_run FOREIGN KEY (run_id)
            REFERENCES accounting.reconciliation_run(id) ON DELETE CASCADE,
        CONSTRAINT fk_rm_source FOREIGN KEY (source_item_id)
            REFERENCES accounting.reconciliation_item(id) ON DELETE CASCADE,
        CONSTRAINT fk_rm_target FOREIGN KEY (target_item_id)
            REFERENCES accounting.reconciliation_item(id) ON DELETE CASCADE,
        CONSTRAINT ck_rm_type CHECK (
            match_type IN ('exact', 'fuzzy', 'partial', 'unmatched_ledger', 'unmatched_bank')
        ),
        CONSTRAINT ck_rm_confidence CHECK (
            confidence_score >= 0 AND confidence_score <= 1
        )
    );
    """)

    # ── reconciliation_gap ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.reconciliation_gap (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        run_id              UUID            NOT NULL,
        severity            VARCHAR(10)     NOT NULL,
        gap_type            VARCHAR(30)     NOT NULL,
        source_system       VARCHAR(30)     NOT NULL,
        affected_entity_id  UUID            NULL,
        amount              NUMERIC(16,2)   NOT NULL DEFAULT 0,
        direction           VARCHAR(10)     NULL,
        description         TEXT            NOT NULL,
        explanation_trace   JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_reconciliation_gap PRIMARY KEY (id),
        CONSTRAINT fk_rg_run FOREIGN KEY (run_id)
            REFERENCES accounting.reconciliation_run(id) ON DELETE CASCADE,
        CONSTRAINT ck_rg_severity CHECK (
            severity IN ('critical', 'warning', 'info')
        ),
        CONSTRAINT ck_rg_type CHECK (
            gap_type IN ('missing_bank_transaction', 'missing_ledger_posting',
                         'timing_difference', 'duplicate_bank_import',
                         'unmatched_tax_projection', 'amount_mismatch',
                         'direction_mismatch', 'date_mismatch', 'other')
        )
    );
    """)

    # ── reconciliation_explanation ──────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.reconciliation_explanation (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        run_id              UUID            NOT NULL,
        entity_type         VARCHAR(10)     NOT NULL,
        entity_id           UUID            NOT NULL,
        matching_rule       VARCHAR(50)     NULL,
        confidence_score    NUMERIC(5,4)    NULL,
        evidence_chain      JSONB           NOT NULL DEFAULT '[]',
        involved_entities   JSONB           NOT NULL DEFAULT '[]',
        delta_explanation   TEXT            NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_reconciliation_explanation PRIMARY KEY (id),
        CONSTRAINT fk_re_run FOREIGN KEY (run_id)
            REFERENCES accounting.reconciliation_run(id) ON DELETE CASCADE,
        CONSTRAINT ck_re_entity CHECK (
            entity_type IN ('match', 'gap')
        )
    );
    """)

    # ── Indexes ─────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_run_company ON accounting.reconciliation_run(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_run_status ON accounting.reconciliation_run(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_run_hash ON accounting.reconciliation_run(run_hash);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_item_run ON accounting.reconciliation_item(run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_item_system ON accounting.reconciliation_item(run_id, system);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_item_checksum ON accounting.reconciliation_item(checksum) WHERE checksum IS NOT NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_match_run ON accounting.reconciliation_match(run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_match_source ON accounting.reconciliation_match(source_item_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_match_target ON accounting.reconciliation_match(target_item_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_gap_run ON accounting.reconciliation_gap(run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_gap_type ON accounting.reconciliation_gap(gap_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_expl_run ON accounting.reconciliation_explanation(run_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rec_expl_entity ON accounting.reconciliation_explanation(entity_type, entity_id);")


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.reconciliation_explanation CASCADE;
    DROP TABLE IF EXISTS accounting.reconciliation_gap CASCADE;
    DROP TABLE IF EXISTS accounting.reconciliation_match CASCADE;
    DROP TABLE IF EXISTS accounting.reconciliation_item CASCADE;
    DROP TABLE IF EXISTS accounting.reconciliation_run CASCADE;
    """)
