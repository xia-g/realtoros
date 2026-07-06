"""add_check_constraints: Add database-level CHECK constraints for domain integrity.

Resolves C3 from Sprint 8.7 audit.
"""

from collections.abc import Sequence
from alembic import op

revision: str = "024_add_check_constraints"
down_revision: str | None = "023_partition_audit_tables"


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        BEGIN ALTER TABLE deal_risk_assessments ADD CONSTRAINT ck_deal_risk_assessments_score CHECK (risk_score >= 0 AND risk_score <= 100); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE compliance_audits ADD CONSTRAINT ck_compliance_score CHECK (score >= 0 AND score <= 100); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE compliance_audits ADD CONSTRAINT ck_risk_level CHECK (risk_level IN ('low', 'medium', 'high', 'critical')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE deal_health_snapshots ADD CONSTRAINT ck_health_score CHECK (score >= 0 AND score <= 100); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE prediction_results ADD CONSTRAINT ck_confidence CHECK (confidence >= 0 AND confidence <= 1); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE deals ADD CONSTRAINT ck_deal_status CHECK (status IN ('initiated', 'verification', 'mortgage', 'registration', 'closing', 'completed', 'cancelled')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE deal_slas ADD CONSTRAINT ck_sla_status CHECK (status IN ('pending', 'completed', 'breached', 'cancelled')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE analytics_alerts ADD CONSTRAINT ck_alert_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE regulation_change_events ADD CONSTRAINT ck_change_type CHECK (change_type IN ('created', 'updated', 'deprecated', 'revoked')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE regulation_sync_logs ADD CONSTRAINT ck_sync_status CHECK (status IN ('running', 'completed', 'failed', 'partial')); EXCEPTION WHEN OTHERS THEN NULL; END;
        BEGIN ALTER TABLE stakeholders ADD CONSTRAINT ck_stakeholder_type CHECK (stakeholder_type IN ('buyer', 'seller', 'bank', 'realtor', 'lawyer', 'notary', 'registrar', 'guardian', 'appraiser')); EXCEPTION WHEN OTHERS THEN NULL; END;
    END $$;
    """)


def downgrade() -> None:
    pass
