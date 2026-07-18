"""032_reporting_schema: Create reporting layer tables for Phase 5.

New tables (accounting schema):
  - report_template              (catalog of regulatory form templates)
  - report_template_version      (versioned, immutable templates)
  - report_draft                 (generated report, materialized projection)
  - report_cell                  (individual values with source_hash)
  - report_audit_result          (AI audit findings)
  - report_audit_finding         (individual finding per audit)
  - submission_package           (submission transport artifact)

Invariants:
  - Report = f(TaxRegister, TemplateVersion) — deterministic
  - AI Audit is read-only (cannot affect report content/status beyond AI_REVIEWED)
  - Submission does not own the report (submission_id ≠ report_id)
  - report_rendering ≠ report_storage (PDF/XML derived from structured cells)
"""

from collections.abc import Sequence

from alembic import op

revision: str = "032_reporting_schema"
down_revision: str | None = "031_tax_schema"


def upgrade() -> None:
    # ── report_template ────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_template (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        code            VARCHAR(50)     NOT NULL,
        name            VARCHAR(200)    NOT NULL,
        description     TEXT            NULL,
        tax_regime      VARCHAR(20)     NOT NULL,
        is_active       BOOLEAN         NOT NULL DEFAULT true,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_template PRIMARY KEY (id),
        CONSTRAINT uq_report_template_code UNIQUE (code),
        CONSTRAINT ck_report_template_regime CHECK (
            tax_regime IN ('USN_D', 'USN_DR', 'GENERAL', 'PATENT')
        )
    );
    """)

    # ── report_template_version ────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_template_version (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        template_id         UUID            NOT NULL,
        version             VARCHAR(30)     NOT NULL,
        status              VARCHAR(20)     NOT NULL DEFAULT 'fetched',
        effective_from      DATE            NOT NULL,
        effective_to        DATE            NULL,
        checksum            VARCHAR(64)     NOT NULL,
        schema_version      VARCHAR(30)     NOT NULL DEFAULT '1.0',
        origin              VARCHAR(100)    NOT NULL DEFAULT 'nalog.ru',
        locale              VARCHAR(10)     NOT NULL DEFAULT 'ru_RU',
        fields_json         JSONB           NOT NULL DEFAULT '{}',
        formulas_json       JSONB           NOT NULL DEFAULT '{}',
        control_ratios      JSONB           NOT NULL DEFAULT '[]',
        metadata_json       JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_template_version PRIMARY KEY (id),
        CONSTRAINT uq_template_version UNIQUE (template_id, version),
        CONSTRAINT fk_rtv_template FOREIGN KEY (template_id)
            REFERENCES accounting.report_template(id) ON DELETE CASCADE,
        CONSTRAINT ck_rtv_status CHECK (
            status IN ('discovered', 'fetched', 'validated', 'active', 'deprecated', 'archived')
        ),
        CONSTRAINT ck_rtv_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
    );
    """)

    # ── report_draft (materialized projection) ─────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_draft (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        report_version      INTEGER         NOT NULL DEFAULT 1,
        company_id          UUID            NOT NULL,
        template_version_id UUID            NOT NULL,
        register_version_id UUID            NULL,
        tax_policy_version  VARCHAR(30)     NULL,
        tax_period_id       UUID            NULL,
        status              VARCHAR(25)     NOT NULL DEFAULT 'draft',
        report_hash         VARCHAR(64)     NOT NULL,
        generated_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
        total_income        NUMERIC(20,2)   NULL,
        total_expense       NUMERIC(20,2)   NULL,
        total_tax           NUMERIC(20,2)   NULL,
        metadata_json       JSONB           NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_draft PRIMARY KEY (id),
        CONSTRAINT fk_rd_template_version FOREIGN KEY (template_version_id)
            REFERENCES accounting.report_template_version(id) ON DELETE RESTRICT,
        CONSTRAINT ck_report_draft_status CHECK (
            status IN ('draft', 'validated', 'ai_reviewed',
                       'accountant_approved', 'ready_to_submit', 'submitted')
        ),
        CONSTRAINT uq_report_version UNIQUE (id, report_version)
    );
    """)

    # ── report_cell (individual values with source_hash) ───────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_cell (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        report_id       UUID            NOT NULL,
        cell_code       VARCHAR(100)    NOT NULL,
        value           TEXT            NULL,
        value_numeric   NUMERIC(20,2)   NULL,
        source_hash     VARCHAR(64)     NOT NULL,
        template_field_id VARCHAR(100)  NULL,
        formula_applied TEXT            NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_cell PRIMARY KEY (id),
        CONSTRAINT fk_rc_report FOREIGN KEY (report_id)
            REFERENCES accounting.report_draft(id) ON DELETE CASCADE,
        CONSTRAINT uq_report_cell UNIQUE (report_id, cell_code)
    );
    """)

    # ── report_audit_result ────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_audit_result (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        report_id           UUID            NOT NULL,
        audit_model_version VARCHAR(30)     NOT NULL,
        risk_score          NUMERIC(5,4)    NOT NULL DEFAULT 0,
        approved            BOOLEAN         NOT NULL DEFAULT false,
        supersedes          UUID            NULL,
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_audit_result PRIMARY KEY (id),
        CONSTRAINT fk_rar_report FOREIGN KEY (report_id)
            REFERENCES accounting.report_draft(id) ON DELETE CASCADE,
        CONSTRAINT ck_risk_score CHECK (risk_score >= 0 AND risk_score <= 1),
        CONSTRAINT fk_rar_supersedes FOREIGN KEY (supersedes)
            REFERENCES accounting.report_audit_result(id) ON DELETE SET NULL
    );
    """)

    # ── report_audit_finding ───────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.report_audit_finding (
        id                  UUID            NOT NULL DEFAULT gen_random_uuid(),
        audit_result_id     UUID            NOT NULL,
        severity            VARCHAR(10)     NOT NULL,
        category            VARCHAR(20)     NOT NULL,
        field_path          VARCHAR(200)    NULL,
        description         TEXT            NOT NULL,
        evidence            TEXT            NULL,
        suggested_action    VARCHAR(30)     NOT NULL DEFAULT 'none',
        created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_report_audit_finding PRIMARY KEY (id),
        CONSTRAINT fk_raf_audit FOREIGN KEY (audit_result_id)
            REFERENCES accounting.report_audit_result(id) ON DELETE CASCADE,
        CONSTRAINT ck_finding_severity CHECK (
            severity IN ('critical', 'warning', 'info')
        ),
        CONSTRAINT ck_finding_category CHECK (
            category IN ('formal', 'logical', 'contextual', 'cross_check')
        ),
        CONSTRAINT ck_finding_action CHECK (
            suggested_action IN ('verify', 'recalculate', 'exclude', 'none')
        )
    );
    """)

    # ── submission_package (transport artifact) ────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.submission_package (
        id                      UUID            NOT NULL DEFAULT gen_random_uuid(),
        report_id               UUID            NOT NULL,
        report_version          INTEGER         NOT NULL,
        transport_payload_hash  VARCHAR(64)     NOT NULL,
        payload_format          VARCHAR(10)     NOT NULL DEFAULT 'xml',
        submitted_at            TIMESTAMPTZ     NOT NULL DEFAULT now(),
        external_receipt        VARCHAR(100)    NULL,
        external_status         VARCHAR(20)     NULL,
        metadata_json           JSONB           NULL,
        CONSTRAINT pk_submission_package PRIMARY KEY (id),
        CONSTRAINT fk_sp_report FOREIGN KEY (report_id)
            REFERENCES accounting.report_draft(id) ON DELETE CASCADE
    );
    """)

    # ── Indexes ────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_rd_company ON accounting.report_draft(company_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rd_status ON accounting.report_draft(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rd_template ON accounting.report_draft(template_version_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rd_hash ON accounting.report_draft(report_hash);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rc_report ON accounting.report_cell(report_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rc_cell ON accounting.report_cell(report_id, cell_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rar_report ON accounting.report_audit_result(report_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raf_audit ON accounting.report_audit_finding(audit_result_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sp_report ON accounting.submission_package(report_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rtv_active ON accounting.report_template_version(template_id) WHERE status = 'active';")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rtv_effective ON accounting.report_template_version(template_id, effective_from, effective_to);")


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.submission_package CASCADE;
    DROP TABLE IF EXISTS accounting.report_audit_finding CASCADE;
    DROP TABLE IF EXISTS accounting.report_audit_result CASCADE;
    DROP TABLE IF EXISTS accounting.report_cell CASCADE;
    DROP TABLE IF EXISTS accounting.report_draft CASCADE;
    DROP TABLE IF EXISTS accounting.report_template_version CASCADE;
    DROP TABLE IF EXISTS accounting.report_template CASCADE;
    """)
