-- =============================================================================
-- Accounting Core v4 — DDL (PostgreSQL)
-- Schema: accounting
-- =============================================================================
-- v4 additions:
--   • processing_state: NEW, RECOGNIZING, READY_FOR_DECISION, DECIDING, DONE, FAILED
--   • decision_explanation — детализация каждого правила
--   • recognition_snapshot — слепок входных данных (immutable)
--   • event_fingerprint — дедупликация (SHA256 хеш)
--   • Rule Engine — выделен как модуль (не в DDL)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS accounting;

-- =============================================================================
-- ENUMS
-- =============================================================================
CREATE TYPE accounting.tax_regime_type AS ENUM ('usn_income','usn_income_expense','osno','psn');
CREATE TYPE accounting.tax_period_type AS ENUM ('month','quarter','year');
CREATE TYPE accounting.period_status AS ENUM ('open','locked','closed');
CREATE TYPE accounting.event_type AS ENUM (
    'bank_inflow','bank_outflow','sale','purchase',
    'client_payment','agent_commission','refund','transfer','manual'
);
CREATE TYPE accounting.recognition_status AS ENUM ('pending','recognized','confirmed','rejected');
CREATE TYPE accounting.match_type AS ENUM ('auto','manual','rule');
CREATE TYPE accounting.doc_role AS ENUM ('primary','confirming','vat','attachment');
CREATE TYPE accounting.batch_status AS ENUM ('pending','processing','completed','failed');
CREATE TYPE accounting.superseded_reason AS ENUM (
    'ocr_correction','manual_fix','rule_change',
    'document_updated','bank_reimport','recalculation'
);
CREATE TYPE accounting.decision_state AS ENUM ('pending','included','excluded','review_required');
CREATE TYPE accounting.processing_state AS ENUM (
    'new','recognizing','ready_for_decision','deciding','done','failed'
);

-- =============================================================================
-- TABLES
-- =============================================================================

-- tax_regime
CREATE TABLE accounting.tax_regime (
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

-- tax_period
CREATE TABLE accounting.tax_period (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    period_type accounting.tax_period_type NOT NULL,
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    status accounting.period_status NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_tax_period PRIMARY KEY (id)
);

-- accounting_batch
CREATE TABLE accounting.accounting_batch (
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

-- accounting_event (центральная сущность)
CREATE TABLE accounting.accounting_event (
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

    -- Версионирование
    version INTEGER NOT NULL DEFAULT 1,
    superseded_by UUID NULL,
    superseded_reason accounting.superseded_reason NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,

    -- Decision state (UI)
    current_decision_id UUID NULL,
    decision_state accounting.decision_state NOT NULL DEFAULT 'pending',

    -- Processing state (очередь)
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

-- accounting_decision
CREATE TABLE accounting.accounting_decision (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    event_id          UUID            NOT NULL,
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

-- decision_explanation (новая — детализация правил)
CREATE TABLE accounting.decision_explanation (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL,
    rule_code VARCHAR(50) NOT NULL,
    weight NUMERIC(5,4) NOT NULL DEFAULT 0,
    message TEXT NULL,
    payload_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_decision_explanation PRIMARY KEY (id)
);

-- recognition_snapshot (новая — слепок входных данных)
CREATE TABLE accounting.recognition_snapshot (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    snapshot_version INTEGER NOT NULL DEFAULT 1,
    inputs_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_recognition_snapshot PRIMARY KEY (id)
);

-- event_transaction
CREATE TABLE accounting.event_transaction (
    event_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    match_type accounting.match_type NOT NULL DEFAULT 'auto',
    confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_event_transaction PRIMARY KEY (event_id, transaction_id)
);

-- event_document
CREATE TABLE accounting.event_document (
    event_id UUID NOT NULL,
    document_id UUID NOT NULL,
    role accounting.doc_role NOT NULL DEFAULT 'confirming',
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_event_document PRIMARY KEY (event_id, document_id, role)
);

-- =============================================================================
-- FOREIGN KEYS
-- =============================================================================
ALTER TABLE accounting.tax_regime            ADD CONSTRAINT fk_tax_regime_company   FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
ALTER TABLE accounting.tax_period            ADD CONSTRAINT fk_tax_period_company   FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
ALTER TABLE accounting.accounting_batch      ADD CONSTRAINT fk_batch_company        FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
ALTER TABLE accounting.accounting_event      ADD CONSTRAINT fk_event_company        FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;
ALTER TABLE accounting.accounting_event      ADD CONSTRAINT fk_event_batch          FOREIGN KEY (batch_id)   REFERENCES accounting.accounting_batch(id) ON DELETE CASCADE;
ALTER TABLE accounting.accounting_decision   ADD CONSTRAINT fk_decision_event       FOREIGN KEY (event_id)   REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
ALTER TABLE accounting.decision_explanation  ADD CONSTRAINT fk_explanation_decision FOREIGN KEY (decision_id) REFERENCES accounting.accounting_decision(id) ON DELETE CASCADE;
ALTER TABLE accounting.recognition_snapshot  ADD CONSTRAINT fk_snapshot_event       FOREIGN KEY (event_id)   REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
ALTER TABLE accounting.event_transaction     ADD CONSTRAINT fk_et_event             FOREIGN KEY (event_id)   REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;
ALTER TABLE accounting.event_document        ADD CONSTRAINT fk_ed_event             FOREIGN KEY (event_id)   REFERENCES accounting.accounting_event(id) ON DELETE CASCADE;

-- =============================================================================
-- UNIQUE CONSTRAINTS
-- =============================================================================
ALTER TABLE accounting.accounting_event
    ADD CONSTRAINT uq_event_fingerprint
    UNIQUE (company_id, event_fingerprint, is_current)
    WHERE is_current = true;

ALTER TABLE accounting.accounting_event
    ADD CONSTRAINT uq_event_source_active
    UNIQUE (source_system, source_type, source_id, event_type, is_current)
    WHERE is_current = true;

ALTER TABLE accounting.accounting_decision
    ADD CONSTRAINT uq_decision_active
    UNIQUE (event_id) WHERE superseded_at IS NULL;

ALTER TABLE accounting.accounting_batch
    ADD CONSTRAINT uq_batch_external_key
    UNIQUE (external_batch_key) WHERE external_batch_key IS NOT NULL;

ALTER TABLE accounting.tax_regime
    ADD CONSTRAINT uq_regime_company_valid_from
    UNIQUE (company_id, valid_from);

ALTER TABLE accounting.tax_period
    ADD CONSTRAINT uq_period_company_type_date
    UNIQUE (company_id, period_type, date_from);

-- =============================================================================
-- CHECK CONSTRAINTS
-- =============================================================================
ALTER TABLE accounting.tax_regime   ADD CONSTRAINT ck_regime_dates   CHECK (valid_to IS NULL OR valid_to > valid_from);
ALTER TABLE accounting.tax_period   ADD CONSTRAINT ck_period_dates   CHECK (date_to > date_from);
ALTER TABLE accounting.event_transaction ADD CONSTRAINT ck_confidence_range CHECK (confidence >= 0 AND confidence <= 1);

-- =============================================================================
-- ИНДЕКСЫ
-- =============================================================================
CREATE INDEX idx_tax_regime_company      ON accounting.tax_regime(company_id);
CREATE INDEX idx_tax_regime_valid_from   ON accounting.tax_regime(valid_from);
CREATE INDEX idx_tax_regime_active       ON accounting.tax_regime(company_id, is_active) WHERE is_active = true;
CREATE INDEX idx_tax_period_company      ON accounting.tax_period(company_id);
CREATE INDEX idx_tax_period_open         ON accounting.tax_period(company_id, status) WHERE status = 'open';

CREATE INDEX idx_batch_company           ON accounting.accounting_batch(company_id);
CREATE INDEX idx_batch_status            ON accounting.accounting_batch(status);
CREATE INDEX idx_batch_external_key      ON accounting.accounting_batch(external_batch_key) WHERE external_batch_key IS NOT NULL;

CREATE INDEX idx_event_company           ON accounting.accounting_event(company_id);
CREATE INDEX idx_event_date              ON accounting.accounting_event(event_date);
CREATE INDEX idx_event_source            ON accounting.accounting_event(source_system, source_type, source_id);
CREATE INDEX idx_event_status            ON accounting.accounting_event(recognition_status);
CREATE INDEX idx_event_current           ON accounting.accounting_event(company_id, is_current) WHERE is_current = true;
CREATE INDEX idx_event_company_date      ON accounting.accounting_event(company_id, event_date DESC);
CREATE INDEX idx_event_decision_state    ON accounting.accounting_event(company_id, decision_state);
CREATE INDEX idx_event_processing        ON accounting.accounting_event(processing_state, next_retry_at)
    WHERE processing_state IN ('new','recognizing','ready_for_decision','deciding','failed');

CREATE INDEX idx_decision_event          ON accounting.accounting_decision(event_id);
CREATE INDEX idx_decision_included       ON accounting.accounting_decision(included);
CREATE INDEX idx_explanation_decision    ON accounting.decision_explanation(decision_id);
CREATE INDEX idx_explanation_rule        ON accounting.decision_explanation(rule_code);
CREATE INDEX idx_snapshot_event          ON accounting.recognition_snapshot(event_id);

CREATE INDEX idx_et_transaction          ON accounting.event_transaction(transaction_id);
CREATE INDEX idx_ed_document             ON accounting.event_document(document_id);

-- =============================================================================
-- ПАРТИЦИОНИРОВАНИЕ
-- =============================================================================
CREATE OR REPLACE FUNCTION accounting.create_monthly_partition(p_month DATE DEFAULT date_trunc('month', CURRENT_DATE)::DATE)
RETURNS VOID AS $$
DECLARE
    v_part_name TEXT;
    v_from      DATE;
    v_to        DATE;
BEGIN
    v_from := date_trunc('month', p_month)::DATE;
    v_to   := (v_from + INTERVAL '1 month')::DATE;
    v_part_name := 'accounting_event_' || to_char(v_from, 'YYYY_MM');
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = v_part_name) THEN
        EXECUTE format(
            'CREATE TABLE accounting.%I PARTITION OF accounting.accounting_event
             FOR VALUES FROM (%L) TO (%L)',
            v_part_name, v_from, v_to
        );
        -- Create per-partition unique indexes (required because parent is partitioned)
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_event_fingerprint_%s
             ON accounting.%I(company_id, event_fingerprint, is_current)
             WHERE is_current = true',
            to_char(v_from, 'YYYY_MM'), v_part_name
        );
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_event_source_active_%s
             ON accounting.%I(source_system, source_type, source_id, event_type, is_current)
             WHERE is_current = true',
            to_char(v_from, 'YYYY_MM'), v_part_name
        );
        RAISE NOTICE 'Partition % created with dedup indexes', v_part_name;
END;
$$ LANGUAGE plpgsql;
