"""prepare_audit_partitioning: Partition audit tables for 10M+ rows.

Prepares:
- ai_call_log → monthly partition by created_at
- agent_tool_calls → monthly partition by created_at
- compliance_audits → monthly partition by created_at

NOTE: Actual partition tables must be created via:
  backend/scripts/execute_partitioning.sql

This migration only adds documentation comments.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018_prepare_audit_partitioning"
down_revision: str | None = "017_add_compliance_audit_and_reg_mapping"


def upgrade() -> None:
    # Add documentation comments about partitioning strategy
    op.execute("""
        COMMENT ON TABLE ai_call_log IS
        'd6d/ai-call-log; partition strategy: monthly by created_at; threshold: 5M rows'
    """)
    op.execute("""
        COMMENT ON TABLE agent_tool_calls IS
        'd6d/agent-tool-calls; partition strategy: monthly by created_at; threshold: 10M rows'
    """)
    op.execute("""
        COMMENT ON TABLE compliance_audits IS
        'd6d/compliance-audits; partition strategy: monthly by created_at; threshold: 5M rows'
    """)


def downgrade() -> None:
    pass
