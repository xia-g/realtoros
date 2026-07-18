"""add_leads_and_soft_delete: Create leads/lead_events, add soft delete.

Revision ID: 002
Revises: 001_initial_schema
Create Date: 2026-06-07

Approved changes per database_hardening_final_review.md:
  1. pg_trgm extension
  2. Soft delete (deleted_at on 10 tables)
  3. Partial unique indexes (WHERE deleted_at IS NULL)
  4. Remove 4 redundant indexes
  5. Add 4 missing FK indexes
  6. Update clients CHECK constraints (ADR-0013)
  7. Create leads + lead_events tables (ADR-0013)
  8. Add created_by to 4 tables (ADR-0010)
  9. Add COMMENT ON (ADR-0010)
  10. Partial indexes for soft delete
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_leads_and_soft_delete"
down_revision: Union[str, Sequence[str], None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. EXTENSIONS ─────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── 2. SOFT DELETE — Add deleted_at to all 10 tables ──────────
    for table in ("roles", "users", "clients", "client_contacts",
                  "properties", "deals", "deal_participants",
                  "documents", "communications", "tasks"):
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ── 3. UNIQUE → PARTIAL UNIQUE INDEXES ────────────────────────
    # Users
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_phone_key")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key")
    # Clients
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_phone_key")

    # Create partial unique indexes
    op.create_index(
        "uq_users_phone_active", "users", ["phone"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_email_active", "users", ["email"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_telegram_id_active", "users", ["telegram_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_clients_phone_active", "clients", ["phone"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── 4. REMOVE REDUNDANT INDEXES ───────────────────────────────
    for idx in ("idx_users_phone", "idx_users_email",
                "idx_users_telegram_id", "idx_clients_phone"):
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # ── 5. ADD MISSING FK INDEXES ─────────────────────────────────
    op.create_index("idx_deals_created_by", "deals", ["created_by"])
    op.create_index("idx_communications_created_by", "communications", ["created_by"])
    op.create_index("idx_tasks_created_by", "tasks", ["created_by"])
    op.create_index("idx_tasks_completed_by", "tasks", ["completed_by"])

    # ── 6. UPDATE CLIENTS CHECK CONSTRAINTS (ADR-0013) ────────────
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS valid_client_status")
    op.execute(
        "ALTER TABLE clients ADD CONSTRAINT valid_client_status "
        "CHECK (status IN ('active', 'inactive', 'archived', 'blacklisted'))"
    )
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS valid_client_source")
    op.execute(
        "ALTER TABLE clients ADD CONSTRAINT valid_client_source "
        "CHECK (source IN ('referral', 'site', 'telegram', 'call', 'other', 'lead_conversion'))"
    )

    # ── 7. CREATE ENUM TYPES FOR LEADS (ADR-0013) ─────────────────
    # Types are created automatically by SQLAlchemy when table is created below.
    # Explicit CREATE TYPE is not needed and causes duplicate errors.

    # ── 7a. CREATE LEADS TABLE (ADR-0013) ─────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source", postgresql.ENUM("telegram", "avito", "cian", "referral", "site", "call", "manual", name="lead_source"), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telegram_id", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("interest_type", postgresql.ENUM("buy", "rent_short", "rent_long", "sell", "commercial_buy", "commercial_rent", "unknown", name="interest_type"), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("property_type", sa.String(20), nullable=True),
        sa.Column("budget_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("budget_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("locations", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("status", postgresql.ENUM("new", "contact_made", "qualifying", "qualified", "converted", "lost", "spam", name="lead_status"), nullable=False, server_default=sa.text("'new'")),
        sa.Column("previous_status", postgresql.ENUM("new", "contact_made", "qualifying", "qualified", "converted", "lost", "spam", name="lead_status"), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), server_default=sa.text("0.0"), nullable=True),
        sa.Column("score_components", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("score_version", sa.String(20), nullable=True),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(10), server_default=sa.text("'cold'"), nullable=True),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_auto_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qualified_by", sa.UUID(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qualification_note", sa.Text(), nullable=True),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deal_id", sa.UUID(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["qualified_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )

    # Leads CHECK constraints
    op.execute("ALTER TABLE leads ADD CONSTRAINT valid_lead_score CHECK (score >= 0 AND score <= 1)")
    op.execute("ALTER TABLE leads ADD CONSTRAINT valid_lead_budget_min CHECK (budget_min IS NULL OR budget_min >= 0)")
    op.execute("ALTER TABLE leads ADD CONSTRAINT valid_lead_budget_max CHECK (budget_max IS NULL OR budget_max >= 0)")

    # Leads partial unique index
    op.create_index(
        "uq_leads_source", "leads", ["source", "source_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Leads indexes
    op.create_index("idx_leads_source_status", "leads", ["source", "status"])
    op.create_index("idx_leads_client", "leads", ["client_id"], postgresql_where=sa.text("client_id IS NOT NULL"))
    op.create_index("idx_leads_assigned", "leads", ["assigned_to"], postgresql_where=sa.text("assigned_to IS NOT NULL"))
    op.create_index("idx_leads_score", "leads", [sa.text("score DESC")], postgresql_where=sa.text("status NOT IN ('converted', 'lost', 'spam')"))
    op.create_index("idx_leads_priority", "leads", ["priority"], postgresql_where=sa.text("status NOT IN ('converted', 'lost', 'spam')"))
    op.create_index("idx_leads_created", "leads", [sa.text("created_at DESC")])
    op.create_index("idx_leads_source_id", "leads", ["source", "source_id"])
    op.create_index("idx_leads_source_created", "leads", ["source", sa.text("created_at DESC")])
    op.create_index("idx_leads_assigned_created", "leads", ["assigned_to", sa.text("created_at DESC")])
    op.create_index("idx_leads_phone", "leads", ["phone"], postgresql_where=sa.text("phone IS NOT NULL"))
    op.create_index("idx_leads_telegram", "leads", ["telegram_id"], postgresql_where=sa.text("telegram_id IS NOT NULL"))

    # ── 7b. CREATE LEAD_EVENTS TABLE (ADR-0013) ────────────────────
    op.create_table(
        "lead_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_status", postgresql.ENUM("new", "contact_made", "qualifying", "qualified", "converted", "lost", "spam", name="lead_status"), nullable=True),
        sa.Column("to_status", postgresql.ENUM("new", "contact_made", "qualifying", "qualified", "converted", "lost", "spam", name="lead_status"), nullable=True),
        sa.Column("from_priority", sa.String(10), nullable=True),
        sa.Column("to_priority", sa.String(10), nullable=True),
        sa.Column("from_score", sa.Float(), nullable=True),
        sa.Column("to_score", sa.Float(), nullable=True),
        sa.Column("score_version", sa.String(20), nullable=True),
        sa.Column("from_user_id", sa.UUID(), nullable=True),
        sa.Column("to_user_id", sa.UUID(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_index("idx_lead_events_lead", "lead_events", ["lead_id"])
    op.create_index("idx_lead_events_type", "lead_events", ["event_type"])
    op.create_index("idx_lead_events_created", "lead_events", [sa.text("created_at DESC")])
    op.create_index("idx_lead_events_changed_by", "lead_events", ["changed_by"])

    # ── 8. ADD created_by TO 4 TABLES (ADR-0010) ──────────────────
    op.add_column("clients", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_clients_created_by", "clients", "users", ["created_by"], ["id"], ondelete="SET NULL")

    op.add_column("properties", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_properties_created_by", "properties", "users", ["created_by"], ["id"], ondelete="SET NULL")

    op.add_column("client_contacts", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_client_contacts_created_by", "client_contacts", "users", ["created_by"], ["id"], ondelete="SET NULL")

    op.add_column("deal_participants", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_deal_participants_created_by", "deal_participants", "users", ["created_by"], ["id"], ondelete="SET NULL")

    # ── 9. ADD COMMENT ON (ADR-0010) ──────────────────────────────
    op.execute("COMMENT ON TABLE roles IS 'Системные роли с правами доступа'")
    op.execute("COMMENT ON TABLE users IS 'Пользователи системы — агенты, менеджеры, администраторы'")
    op.execute("COMMENT ON TABLE clients IS 'Клиенты агентства — физические и юридические лица'")
    op.execute("COMMENT ON TABLE client_contacts IS 'Контактные лица клиентов (для юридических лиц)'")
    op.execute("COMMENT ON TABLE properties IS 'Объекты недвижимости — квартиры, дома, коммерция, участки'")
    op.execute("COMMENT ON TABLE deals IS 'Сделки — связывают клиентов и объекты недвижимости'")
    op.execute("COMMENT ON TABLE deal_participants IS 'Участники сделки с ролями (покупатель, продавец и т.д.)'")
    op.execute("COMMENT ON TABLE documents IS 'Документы — договоры, паспорта, выписки, квитанции'")
    op.execute("COMMENT ON TABLE communications IS 'Коммуникации — звонки, сообщения, встречи, заметки'")
    op.execute("COMMENT ON TABLE tasks IS 'Задачи — действия для агентов'")
    op.execute("COMMENT ON TABLE leads IS 'Лиды — потенциальные клиенты из различных источников'")
    op.execute("COMMENT ON TABLE lead_events IS 'События жизненного цикла лида — изменения статуса, скоринга, назначения'")

    op.execute("COMMENT ON COLUMN users.phone IS 'Номер телефона (уникальный среди активных пользователей)'")
    op.execute("COMMENT ON COLUMN users.email IS 'Email (уникальный среди активных пользователей)'")
    op.execute("COMMENT ON COLUMN clients.phone IS 'Номер телефона (уникальный среди активных клиентов)'")
    op.execute("COMMENT ON COLUMN documents.file_hash IS 'SHA-256 хеш файла (глобально уникальный)'")
    op.execute("COMMENT ON COLUMN leads.score IS 'Скоринг лида от 0.0 до 1.0'")
    op.execute("COMMENT ON COLUMN leads.source IS 'Источник лида: telegram, avito, cian, referral и т.д.'")
    op.execute("COMMENT ON COLUMN leads.status IS 'Статус жизненного цикла лида'")

    # ── 10. PARTIAL INDEXES FOR SOFT DELETE ───────────────────────
    for table in ("roles", "users", "clients", "client_contacts",
                  "properties", "deals", "deal_participants",
                  "documents", "communications", "tasks", "leads"):
        op.create_index(
            f"idx_{table}_active", table, ["deleted_at"],
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    # ── 11. DOCUMENTS — global unique index on hash ───────────────
    op.create_index("uq_documents_hash", "documents", ["file_hash"], unique=True)


def downgrade() -> None:
    # ── 11. DOCUMENTS unique index ────────────────────────────────
    op.drop_index("uq_documents_hash", table_name="documents")

    # ── 10. PARTIAL INDEXES FOR SOFT DELETE ───────────────────────
    for table in ("leads", "tasks", "communications", "documents",
                  "deal_participants", "deals", "properties",
                  "client_contacts", "clients", "users", "roles"):
        op.drop_index(f"idx_{table}_active", table_name=table)

    # ── 9. COMMENT ON — dropped implicitly with tables ────────────

    # ── 8. ADDED created_by COLUMNS ────────────────────────────────
    op.drop_constraint("fk_deal_participants_created_by", "deal_participants", type_="foreignkey")
    op.drop_constraint("fk_client_contacts_created_by", "client_contacts", type_="foreignkey")
    op.drop_constraint("fk_properties_created_by", "properties", type_="foreignkey")
    op.drop_constraint("fk_clients_created_by", "clients", type_="foreignkey")
    op.drop_column("deal_participants", "created_by")
    op.drop_column("client_contacts", "created_by")
    op.drop_column("properties", "created_by")
    op.drop_column("clients", "created_by")

    # ── 7b. DROP LEAD_EVENTS ──────────────────────────────────────
    op.drop_table("lead_events")

    # ── 7a. DROP LEADS ────────────────────────────────────────────
    op.drop_table("leads")

    # ── 7. DROP ENUM TYPES ────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS interest_type")
    op.execute("DROP TYPE IF EXISTS lead_status")
    op.execute("DROP TYPE IF EXISTS lead_source")

    # ── 6. RESTORE CLIENT CHECK CONSTRAINTS ───────────────────────
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS valid_client_status")
    op.execute(
        "ALTER TABLE clients ADD CONSTRAINT valid_client_status "
        "CHECK (status IN ('lead', 'active', 'inactive', 'archived', 'blacklisted'))"
    )
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS valid_client_source")
    op.execute(
        "ALTER TABLE clients ADD CONSTRAINT valid_client_source "
        "CHECK (source IN ('referral', 'site', 'telegram', 'call', 'other'))"
    )

    # ── 5. DROP ADDED FK INDEXES ──────────────────────────────────
    op.drop_index("idx_tasks_completed_by", table_name="tasks")
    op.drop_index("idx_tasks_created_by", table_name="tasks")
    op.drop_index("idx_communications_created_by", table_name="communications")
    op.drop_index("idx_deals_created_by", table_name="deals")

    # ── 4. RESTORE REDUNDANT INDEXES ──────────────────────────────
    op.create_index("idx_clients_phone", "clients", ["phone"])
    op.create_index("idx_users_telegram_id", "users", ["telegram_id"])
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_phone", "users", ["phone"])

    # ── 3. RESTORE UNIQUE CONSTRAINTS ─────────────────────────────
    op.drop_index("uq_clients_phone_active", table_name="clients")
    op.drop_index("uq_users_telegram_id_active", table_name="users")
    op.drop_index("uq_users_email_active", table_name="users")
    op.drop_index("uq_users_phone_active", table_name="users")
    op.create_unique_constraint("clients_phone_key", "clients", ["phone"])
    op.create_unique_constraint("users_telegram_id_key", "users", ["telegram_id"])
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_unique_constraint("users_phone_key", "users", ["phone"])

    # ── 2. SOFT DELETE — drop deleted_at columns ──────────────────
    for table in ("tasks", "communications", "documents",
                  "deal_participants", "deals", "properties",
                  "client_contacts", "clients", "users", "roles"):
        op.drop_column(table, "deleted_at")

    # ── 1. EXTENSIONS ─────────────────────────────────────────────
    # pg_trgm is not dropped on downgrade — other tables may depend on it
