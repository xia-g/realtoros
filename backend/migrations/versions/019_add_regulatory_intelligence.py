"""add_regulatory_intelligence: Regulation sources, change events, sync logs.

Revision ID: 019
Revises: 018_prepare_audit_partitioning
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "019_add_regulatory_intelligence"
down_revision: str | None = "018_prepare_audit_partitioning"


def upgrade() -> None:
    op.create_table(
        "regulation_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("trust_level", sa.String(20), nullable=False, server_default="OFFICIAL"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sync_frequency_hours", sa.Integer(), server_default=sa.text("24"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_regulation_sources_code", "regulation_sources", ["code"])
    op.create_index("ix_regulation_sources_source_type", "regulation_sources", ["source_type"])

    op.create_table(
        "regulation_change_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.UUID(), nullable=False),
        sa.Column("version_from", sa.String(20), nullable=True),
        sa.Column("version_to", sa.String(20), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["regulation_id"], ["regulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulation_change_events_regulation_id", "regulation_change_events", ["regulation_id"])
    op.create_index("ix_regulation_change_events_change_type", "regulation_change_events", ["change_type"])

    op.create_table(
        "regulation_sync_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("documents_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("regulations_created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("regulations_updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["regulation_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulation_sync_logs_source_id", "regulation_sync_logs", ["source_id"])

    # Seed default sources
    op.execute("""
        INSERT INTO regulation_sources (id, code, name, source_type, base_url, trust_level, enabled, sync_frequency_hours)
        VALUES
            (gen_random_uuid(), 'rosreestr', 'Росреестр', 'rosreestr', 'https://rosreestr.gov.ru', 'OFFICIAL', true, 24),
            (gen_random_uuid(), 'nalog', 'ФНС России', 'nalog', 'https://nalog.gov.ru', 'OFFICIAL', true, 24),
            (gen_random_uuid(), 'cbr', 'ЦБ РФ', 'cbr', 'https://cbr.ru', 'OFFICIAL', true, 24),
            (gen_random_uuid(), 'government', 'Правительство РФ', 'government_portal', 'https://government.ru', 'OFFICIAL', true, 24),
            (gen_random_uuid(), 'consultant', 'КонсультантПлюс', 'consultant', 'https://consultant.ru', 'VERIFIED', true, 12),
            (gen_random_uuid(), 'garant', 'Гарант', 'garant', 'https://garant.ru', 'VERIFIED', true, 12)
    """)


def downgrade() -> None:
    op.drop_table("regulation_sync_logs")
    op.drop_table("regulation_change_events")
    op.drop_table("regulation_sources")
