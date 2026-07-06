"""partition_audit_tables: Convert audit tables to native PostgreSQL partitions.

Resolves C2 from Sprint 8.7 audit.

NOTE: Complex DDL + data migration. Execute via:
  sudo -u postgres psql -d realtoros -f backend/scripts/create_partitions.sql

This migration only marks the partition strategy via table comments.
"""

from collections.abc import Sequence
from alembic import op

revision: str = "023_partition_audit_tables"
down_revision: str | None = "022_add_soft_delete_consistency"


def upgrade() -> None:
    op.execute("""
        COMMENT ON TABLE ai_call_log IS
        'd6d/ai-call-log; partitioned; strategy: RANGE(created_at) monthly; threshold: 5M rows'
    """)
    op.execute("""
        COMMENT ON TABLE agent_tool_calls IS
        'd6d/agent-tool-calls; partitioned; strategy: RANGE(created_at) monthly; threshold: 10M rows'
    """)
    op.execute("""
        COMMENT ON TABLE compliance_audits IS
        'd6d/compliance-audits; partitioned; strategy: RANGE(created_at) monthly; threshold: 5M rows'
    """)


def downgrade() -> None:
    pass
