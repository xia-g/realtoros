"""026_accounting_schema: Create accounting schema (v4).

v4 additions:
  • processing_state: NEW/RECOGNIZING/READY_FOR_DECISION/DECIDING/DONE/FAILED
  • decision_explanation table — per-rule detail
  • recognition_snapshot table — immutable input snapshot
  • event_fingerprint column — dedup hash
"""

from collections.abc import Sequence
from alembic import op

revision: str = "026_accounting_schema"
down_revision: str | None = "025_fk_lifecycle_hardening"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS accounting;")

    # ── Enums ──────────────────────────────────────────────────────
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tax_regime_type') THEN
            CREATE TYPE accounting.tax_regime_type AS ENUM ('usn_income','usn_income_expense','osno','psn');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tax_period_type') THEN
            CREATE TYPE accounting.tax_period_type AS ENUM ('month','quarter','year');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'period_status') THEN
            CREATE TYPE accounting.period_status AS ENUM ('open','locked','closed');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_type') THEN
            CREATE TYPE accounting.event_type AS ENUM (
                'bank_inflow','bank_outflow','sale','purchase',
                'client_payment','agent_commission','refund','transfer','manual'
            );
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'recognition_status') THEN
            CREATE TYPE accounting.recognition_status AS ENUM ('pending','recognized','confirmed','rejected');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'match_type') THEN
            CREATE TYPE accounting.match_type AS ENUM ('auto','manual','rule');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'doc_role') THEN
            CREATE TYPE accounting.doc_role AS ENUM ('primary','confirming','vat','attachment');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'batch_status') THEN
            CREATE TYPE accounting.batch_status AS ENUM ('pending','processing','completed','failed');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'superseded_reason') THEN
            CREATE TYPE accounting.superseded_reason AS ENUM (
                'ocr_correction','manual_fix','rule_change',
                'document_updated','bank_reimport','recalculation'
            );
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'decision_state') THEN
            CREATE TYPE accounting.decision_state AS ENUM ('pending','included','excluded','review_required');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_state') THEN
            CREATE TYPE accounting.processing_state AS ENUM (
                'new','recognizing','ready_for_decision','deciding','done','failed'
            );
        END IF;
    END $$;
    """)

    # ── tax_regime ─────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_regime (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        company_id UUID NOT NULL,
        regime_type accounting.tax_regime_type NOT NULL,
        valid_from DATE NOT NULL,
        valid_to DATE NULL,
        settings_json JSONB NOT NULL DEFAULT '{}',
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_regime PRIMARY KEY (id)
    );
    """)

    # ── tax_period ─────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.tax_period (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        company_id UUID NOT NULL,
        period_type accounting.tax_period_type NOT NULL,
        date_from DATE NOT NULL,
        date_to DATE NOT NULL,
        status accounting.period_status NOT NULL DEFAULT 'open',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_tax_period PRIMARY KEY (id)
    );
    """)

    # ── accounting_batch ───────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.accounting_batch (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        company_id UUID NOT NULL,
        source VARCHAR(50) NOT NULL,
        external_batch_key VARCHAR(128) NULL,
        checksum VARCHAR(64) NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ NULL,
        status accounting.batch_status NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_accounting_batch PRIMARY KEY (id)
    );
    """)

    # ── accounting_event ───────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.accounting_event (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        company_id UUID NOT NULL,
        batch_id UUID NOT NULL,
        event_type accounting.event_type NOT NULL,
        event_date TIMESTAMPTZ NOT NULL DEFAULT now(),
        amount NUMERIC(16,2) NOT NULL,
        currency CHAR(3) NOT NULL DEFAULT 'RUB',
        source_system VARCHAR(20) NOT NULL,
        source_type VARCHAR(30) NOT NULL,
        source_id VARCHAR(64) NOT NULL,
        event_fingerprint VARCHAR(64) NOT NULL,
        counterparty_id UUID NULL,
        recognition_status accounting.recognition_status NOT NULL DEFAULT 'pending',
        is_tax_relevant BOOLEAN NOT NULL DEFAULT true,
        requires_review BOOLEAN NOT NULL DEFAULT false,
        description TEXT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        superseded_by UUID NULL,
        superseded_reason accounting.superseded_reason NULL,
        is_current BOOLEAN NOT NULL DEFAULT true,
        current_decision_id UUID NULL,
        decision_state accounting.decision_state NOT NULL DEFAULT 'pending',
        processing_state accounting.processing_state NOT NULL DEFAULT 'new',
        next_retry_at TIMESTAMPTZ NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_accounting_event PRIMARY KEY (id, event_date),
        CONSTRAINT ck_amount_positive CHECK (amount > 0),
        CONSTRAINT ck_version_positive CHECK (version >= 1)
    ) PARTITION BY RANGE (event_date);
    """)

    # ── accounting_decision ────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.accounting_decision (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        event_id UUID NOT NULL,
        decision_version  INTEGER         NOT NULL DEFAULT 1,
        ruleset_version   VARCHAR(20)     NOT NULL,
        policy_version    VARCHAR(20)     NOT NULL,
        included BOOLEAN NOT NULL,
        reason TEXT NULL,
        manual_override BOOLEAN NOT NULL DEFAULT false,
        override_by UUID NULL,
        superseded_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_accounting_decision PRIMARY KEY (id)
    );
    """)

    # ── decision_explanation ───────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.decision_explanation (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        decision_id UUID NOT NULL,
        rule_code VARCHAR(50) NOT NULL,
        weight NUMERIC(5,4) NOT NULL DEFAULT 0,
        message TEXT NULL,
        payload_json JSONB NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_decision_explanation PRIMARY KEY (id)
    );
    """)

    # ── recognition_snapshot ───────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.recognition_snapshot (
        id UUID NOT NULL DEFAULT gen_random_uuid(),
        event_id UUID NOT NULL,
        snapshot_version INTEGER NOT NULL DEFAULT 1,
        inputs_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_recognition_snapshot PRIMARY KEY (id)
    );
    """)

    # ── event_transaction ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.event_transaction (
        event_id UUID NOT NULL,
        transaction_id UUID NOT NULL,
        match_type accounting.match_type NOT NULL DEFAULT 'auto',
        confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
        matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_event_transaction PRIMARY KEY (event_id, transaction_id)
    );
    """)

    # ── event_document ─────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.event_document (
        event_id UUID NOT NULL,
        document_id UUID NOT NULL,
        role accounting.doc_role NOT NULL DEFAULT 'confirming',
        added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT pk_event_document PRIMARY KEY (event_id, document_id, role)
    );
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.event_document CASCADE;
    DROP TABLE IF EXISTS accounting.event_transaction CASCADE;
    DROP TABLE IF EXISTS accounting.recognition_snapshot CASCADE;
    DROP TABLE IF EXISTS accounting.decision_explanation CASCADE;
    DROP TABLE IF EXISTS accounting.accounting_decision CASCADE;
    DROP TABLE IF EXISTS accounting.accounting_event CASCADE;
    DROP TABLE IF EXISTS accounting.accounting_batch CASCADE;
    DROP TABLE IF EXISTS accounting.tax_period CASCADE;
    DROP TABLE IF EXISTS accounting.tax_regime CASCADE;
    DROP SCHEMA IF EXISTS accounting CASCADE;
    """)
