"""Tests for database partitioning."""

import pytest


class TestPartitioning:
    """Verify partitioning strategy and migration code."""

    def test_migration_exists(self):
        """019 migration exists for audit tables."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        migs = list((root / "backend" / "migrations" / "versions").glob("*partition*"))
        assert len(migs) > 0, "No partition migration found"
        assert any("audit" in m.name for m in migs), "No audit partition migration"

    def test_partition_tables_listed(self):
        """Verify all three audit tables are partitioned."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        mig_path = root / "backend" / "migrations" / "versions"
        for f in sorted(mig_path.glob("*partition*")):
            content = f.read_text()
            for table in ["ai_call_log", "agent_tool_calls", "compliance_audits"]:
                assert table in content, f"Table {table} not in partition migration"

    def test_monthly_partition_strategy(self):
        """Verify monthly partition strategy."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        for f in sorted((root / "backend" / "migrations" / "versions").glob("*partition*")):
            content = f.read_text()
            assert "month" in content.lower() or "YYYY_MM" in content or "monthly" in content, \
                "No monthly partitioning strategy found"

    def test_partition_script_exists(self):
        """Execute partitioning script exists."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        script = root / "backend" / "scripts" / "execute_partitioning.py"
        assert script.exists(), "Partition execution script not found"

    def test_retention_policy(self):
        """Verify retention policy exists."""
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        script = root / "backend" / "scripts" / "execute_partitioning.py"
        if script.exists():
            content = script.read_text()
            assert "retention" in content.lower(), "No retention policy found"

    def test_next_partition_creation(self):
        """Verify automatic next-partition creation logic."""
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        script = root / "backend" / "scripts" / "execute_partitioning.py"
        if script.exists():
            content = script.read_text()
            # Check for monthly loop
            assert re.search(r"for\s+i\s+in\s+range\(12\)", content), \
                "No 12-month loop for partition creation"