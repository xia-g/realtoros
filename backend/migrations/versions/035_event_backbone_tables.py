"""035_event_backbone_tables: Stream 3 — Event Backbone tables.

New tables:
  - event_outbox                 (mutable queue for Publisher)
  - business_events              (append-only event log)
  - consumer_processed_events    (consumer idempotency tracking)

See: Proposal §5, Architecture Freeze.
"""

from collections.abc import Sequence
from alembic import op

revision: str = "035_event_backbone_tables"
down_revision: str | None = "034_control_plane_schema"


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        -- ── event_outbox ────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS event_outbox (
            id              UUID            NOT NULL DEFAULT gen_random_uuid(),
            event_type      VARCHAR(100)    NOT NULL,
            aggregate_type  VARCHAR(50)     NOT NULL,
            aggregate_id    VARCHAR(255)    NOT NULL,
            payload         JSONB           NOT NULL,
            metadata        JSONB           NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
            published_at    TIMESTAMPTZ,
            attempts        INTEGER         NOT NULL DEFAULT 0,
            last_error      TEXT,
            status          VARCHAR(20)     NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'published', 'failed', 'dead')),

            CONSTRAINT pk_event_outbox PRIMARY KEY (id)
        );

        -- For polling pending events
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_outbox_status_created') THEN
            CREATE INDEX idx_outbox_status_created
                ON event_outbox (status, created_at)
                WHERE status = 'pending';
        END IF;

        -- For recovery failed events
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_outbox_status_attempts') THEN
            CREATE INDEX idx_outbox_status_attempts
                ON event_outbox (status, attempts)
                WHERE status = 'failed';
        END IF;

        -- ── business_events (append-only event log) ─────────────────
        CREATE TABLE IF NOT EXISTS business_events (
            event_id        UUID            NOT NULL,
            event_type      VARCHAR(100)    NOT NULL,
            aggregate_type  VARCHAR(50)     NOT NULL,
            aggregate_id    VARCHAR(255)    NOT NULL,
            occurred_at     TIMESTAMPTZ     NOT NULL,
            version         INTEGER         NOT NULL DEFAULT 1,
            payload         JSONB           NOT NULL,
            metadata        JSONB           NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

            CONSTRAINT pk_business_events PRIMARY KEY (event_id)
        );

        -- For replay by aggregate
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_be_aggregate') THEN
            CREATE INDEX idx_be_aggregate
                ON business_events (aggregate_type, aggregate_id, occurred_at);
        END IF;

        -- For replay by type
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_be_event_type') THEN
            CREATE INDEX idx_be_event_type
                ON business_events (event_type, occurred_at);
        END IF;

        -- For replay by time
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_be_occurred_at') THEN
            CREATE INDEX idx_be_occurred_at
                ON business_events (occurred_at);
        END IF;

        -- ── consumer_processed_events ───────────────────────────────
        CREATE TABLE IF NOT EXISTS consumer_processed_events (
            consumer_name   VARCHAR(100)    NOT NULL,
            event_id        UUID            NOT NULL,
            processed_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),

            CONSTRAINT pk_consumer_processed PRIMARY KEY (consumer_name, event_id)
        );
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS consumer_processed_events;
    DROP TABLE IF EXISTS business_events;
    DROP TABLE IF EXISTS event_outbox;
    """)
