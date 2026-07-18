"""034_control_plane_schema: Operational Control Plane for Phase 7.

New tables (accounting schema):
  - system_state              (global system health + period state)
  - control_action            (immutable log of all control operations)
  - approval_workflow         (pending + completed approval workflows)
  - system_metrics_snapshot   (periodic metric snapshots for observability)

Invariants:
  - Control Plane does NOT compute data — only manages states/processes
  - Every action is logged as an immutable audit event
  - AI never has approval rights
  - System state does NOT affect data, only processes
"""

from collections.abc import Sequence
from alembic import op

revision: str = "034_control_plane_schema"
down_revision: str | None = "033_reconciliation_schema"


def upgrade() -> None:
    # ── system_state ────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.system_state (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        subsystem       VARCHAR(20)     NOT NULL,
        status          VARCHAR(15)     NOT NULL DEFAULT 'healthy',
        state_hash      VARCHAR(64)     NOT NULL,
        details_json    JSONB           NULL,
        updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_system_state PRIMARY KEY (id),
        CONSTRAINT uq_system_state_subsystem UNIQUE (subsystem),
        CONSTRAINT ck_system_state_subsystem CHECK (
            subsystem IN ('ledger', 'tax', 'reports', 'reconciliation', 'global')
        ),
        CONSTRAINT ck_system_state_status CHECK (
            status IN ('healthy', 'degraded', 'replaying', 'recalculating',
                       'locked', 'error')
        )
    );
    """)

    # ── control_action (immutable audit log) ────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.control_action (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        action_type     VARCHAR(30)     NOT NULL,
        target_system   VARCHAR(20)     NOT NULL,
        actor_id        UUID            NULL,
        actor_role      VARCHAR(20)     NOT NULL DEFAULT 'system_operator',
        status          VARCHAR(15)     NOT NULL DEFAULT 'pending',
        state_before_hash VARCHAR(64)   NULL,
        state_after_hash  VARCHAR(64)   NULL,
        details_json    JSONB           NULL,
        correlation_id  VARCHAR(36)     NULL,
        error_message   TEXT            NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        completed_at    TIMESTAMPTZ     NULL,
        CONSTRAINT pk_control_action PRIMARY KEY (id),
        CONSTRAINT ck_ca_action CHECK (
            action_type IN (
                'close_period', 'open_period',
                'recalculate_tax_registers', 'freeze_tax_policy',
                'regenerate_report', 'revalidate_report',
                'run_reconciliation', 'rerun_failed_matches',
                'full_replay', 'partial_replay', 'system_backfill',
                'approve', 'reject', 'lock_system', 'unlock_system'
            )
        ),
        CONSTRAINT ck_ca_system CHECK (
            target_system IN ('ledger', 'tax', 'reports', 'reconciliation', 'global')
        ),
        CONSTRAINT ck_ca_status CHECK (
            status IN ('pending', 'running', 'completed', 'failed', 'rejected')
        ),
        CONSTRAINT ck_ca_role CHECK (
            actor_role IN ('accountant', 'auditor', 'admin', 'system_operator', 'readonly')
        )
    );
    """)

    # ── approval_workflow ───────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.approval_workflow (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        action_id       UUID            NOT NULL,
        required_role   VARCHAR(20)     NOT NULL,
        status          VARCHAR(15)     NOT NULL DEFAULT 'pending',
        approved_by     UUID            NULL,
        approved_at     TIMESTAMPTZ     NULL,
        reason          TEXT            NULL,
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
        CONSTRAINT pk_approval_workflow PRIMARY KEY (id),
        CONSTRAINT fk_aw_action FOREIGN KEY (action_id)
            REFERENCES accounting.control_action(id) ON DELETE CASCADE,
        CONSTRAINT ck_aw_status CHECK (
            status IN ('pending', 'approved', 'rejected')
        ),
        CONSTRAINT ck_aw_role CHECK (
            required_role IN ('accountant', 'auditor', 'admin', 'system_operator')
        )
    );
    """)

    # ── system_metrics_snapshot ─────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting.system_metrics_snapshot (
        id              UUID            NOT NULL DEFAULT gen_random_uuid(),
        snapshot_time   TIMESTAMPTZ     NOT NULL DEFAULT now(),
        replay_duration_avg    NUMERIC(10,2)  NULL,
        reconciliation_lag    NUMERIC(10,2)  NULL,
        report_gen_time_avg   NUMERIC(10,2)  NULL,
        health_state          VARCHAR(15)    NOT NULL DEFAULT 'healthy',
        failed_jobs_count     INTEGER        NOT NULL DEFAULT 0,
        lock_count            INTEGER        NOT NULL DEFAULT 0,
        total_actions         INTEGER        NOT NULL DEFAULT 0,
        metadata_json         JSONB          NULL,
        created_at            TIMESTAMPTZ    NOT NULL DEFAULT now(),
        CONSTRAINT pk_system_metrics PRIMARY KEY (id)
    );
    """)

    # ── Indexes ─────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_ca_action ON accounting.control_action(action_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ca_system ON accounting.control_action(target_system);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ca_correlation ON accounting.control_action(correlation_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ca_created ON accounting.control_action(created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_aw_action ON accounting.approval_workflow(action_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_aw_status ON accounting.approval_workflow(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sm_time ON accounting.system_metrics_snapshot(snapshot_time DESC);")


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS accounting.system_metrics_snapshot CASCADE;
    DROP TABLE IF EXISTS accounting.approval_workflow CASCADE;
    DROP TABLE IF EXISTS accounting.control_action CASCADE;
    DROP TABLE IF EXISTS accounting.system_state CASCADE;
    """)
