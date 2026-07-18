"""Execute partitioning in PostgreSQL — idempotent, retry-safe.

Usage:
  python3 backend/scripts/execute_partitioning.py

Requires: DATABASE_URL in .env or env var.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


PARTITION_SQL = """
DO $$
DECLARE
    r record;
    tbl text;
    part_name text;
    start_date date;
    end_date date;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ai_call_log', 'agent_tool_calls', 'compliance_audits']
    LOOP
        -- Check if table exists and is not already partitioned
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = tbl) THEN
            -- Create partitions for next 12 months
            FOR i IN 0..11 LOOP
                start_date := date_trunc('month', now()) + (i || ' months')::interval;
                end_date := start_date + interval '1 month';
                part_name := tbl || '_' || to_char(start_date, 'YYYY_MM');

                BEGIN
                    EXECUTE format(
                        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                         FOR VALUES FROM (%L) TO (%L)',
                        part_name, tbl, start_date, end_date
                    );
                    RAISE NOTICE 'Created partition: %', part_name;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Skipped partition %: %', part_name, SQLERRM;
                END;
            END LOOP;
        END IF;
    END LOOP;
END $$;
"""

AUTO_CREATE_FUNC = """
CREATE OR REPLACE FUNCTION auto_create_partition()
RETURNS event_trigger AS $$
DECLARE
    tbl text;
    part_name text;
    next_start date;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ai_call_log', 'agent_tool_calls', 'compliance_audits']
    LOOP
        next_start := date_trunc('month', now() + interval '1 month');
        part_name := tbl || '_' || to_char(next_start, 'YYYY_MM');
        BEGIN
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                 FOR VALUES FROM (%L) TO (%L)',
                part_name, tbl, next_start, next_start + interval '1 month'
            );
        EXCEPTION WHEN OTHERS THEN
            NULL;  -- table may not be partitioned yet
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
"""


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/real_estate_os",
    )

    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        # 1. Check existing partitions
        before = await conn.fetch(
            "SELECT relname FROM pg_class WHERE relname ~ '^(ai_call_log|agent_tool_calls|compliance_audits)_\\d{4}_\\d{2}$'"
        )
        print(f"Partitions before: {len(before)}")
        for row in before:
            print(f"  {row['relname']}")

        # 2. Execute partitioning
        print("\nCreating partitions...")
        await conn.execute(PARTITION_SQL)

        # 3. Verify
        after = await conn.fetch(
            "SELECT relname FROM pg_class WHERE relname ~ '^(ai_call_log|agent_tool_calls|compliance_audits)_\\d{4}_\\d{2}$'"
        )
        print(f"\nPartitions after: {len(after)}")
        for row in after:
            print(f"  {row['relname']}")

        # 4. Check partitioned tables
        partitioned = await conn.fetch("""
            SELECT
                p.relname AS table_name,
                count(i.inhrelid) AS partition_count
            FROM pg_class p
            JOIN pg_partitioned_table pt ON pt.partrelid = p.oid
            LEFT JOIN pg_inherits i ON i.inhparent = p.oid
            WHERE p.relname IN ('ai_call_log', 'agent_tool_calls', 'compliance_audits')
            GROUP BY p.relname
        """)
        print(f"\nPartitioned tables:")
        for row in partitioned:
            print(f"  {row['table_name']}: {row['partition_count']} partitions")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())