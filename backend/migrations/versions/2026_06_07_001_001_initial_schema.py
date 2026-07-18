"""initial_schema: Create all 10 domain model tables.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-06-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── roles ──────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telegram_id", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("telegram_chat_id", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("avatar", sa.String(500), nullable=True),
        sa.Column("settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("telegram_id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
    )

    # ── clients ────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.String(20), server_default=sa.text("'buyer'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'lead'"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telegram_id", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), server_default=sa.text("'other'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )

    # ── client_contacts ────────────────────────────────────────────
    op.create_table(
        "client_contacts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )

    # ── properties ─────────────────────────────────────────────────
    op.create_table(
        "properties",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'available'"), nullable=False),
        sa.Column("deal_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("area_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_living", sa.Numeric(10, 2), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("floors_total", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column("price_currency", sa.String(3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("price_per_meter", sa.Numeric(15, 2), nullable=True),
        sa.Column("commission", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("photos", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("documents", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["clients.id"], ondelete="SET NULL"),
    )

    # ── deals ──────────────────────────────────────────────────────
    op.create_table(
        "deals",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deal_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'negotiation'"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column("price_currency", sa.String(3), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("commission", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=True),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(50), server_default=sa.text("'other'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )

    # ── deal_participants ──────────────────────────────────────────
    op.create_table(
        "deal_participants",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
    )

    # ── documents ──────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("deal_id", sa.UUID(), nullable=True),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
    )

    # ── communications ─────────────────────────────────────────────
    op.create_table(
        "communications",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("communication_type", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("deal_id", sa.UUID(), nullable=True),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("contact", sa.String(255), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("is_important", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )

    # ── tasks ──────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("priority", sa.String(10), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("task_type", sa.String(20), server_default=sa.text("'other'"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("deal_id", sa.UUID(), nullable=True),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.UUID(), nullable=True),
        sa.Column("reminder", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ── CHECK constraints ──────────────────────────────────────
    # users
    op.execute(
        "ALTER TABLE users "
        "ADD CONSTRAINT valid_user_status "
        "CHECK (status IN ('active', 'inactive', 'blocked'))"
    )

    # clients
    op.execute(
        "ALTER TABLE clients "
        "ADD CONSTRAINT valid_client_type "
        "CHECK (type IN ('buyer', 'seller', 'tenant', 'landlord', 'investor', 'partner'))"
    )
    op.execute(
        "ALTER TABLE clients "
        "ADD CONSTRAINT valid_client_status "
        "CHECK (status IN ('lead', 'active', 'inactive', 'archived', 'blacklisted'))"
    )
    op.execute(
        "ALTER TABLE clients "
        "ADD CONSTRAINT valid_client_source "
        "CHECK (source IN ('referral', 'site', 'telegram', 'call', 'other'))"
    )

    # properties
    op.execute(
        "ALTER TABLE properties "
        "ADD CONSTRAINT valid_property_type "
        "CHECK (property_type IN ('apartment', 'house', 'commercial', 'land', 'townhouse', 'penthouse'))"
    )
    op.execute(
        "ALTER TABLE properties "
        "ADD CONSTRAINT valid_property_status "
        "CHECK (status IN ('available', 'under_contract', 'sold', 'rented', 'archived', 'removed'))"
    )
    op.execute(
        "ALTER TABLE properties "
        "ADD CONSTRAINT valid_deal_type "
        "CHECK (deal_type IN ('sale', 'rent_short', 'rent_long', 'commercial'))"
    )
    op.execute(
        "ALTER TABLE properties "
        "ADD CONSTRAINT valid_price_currency "
        "CHECK (price_currency IN ('RUB', 'USD', 'EUR'))"
    )

    # deals
    op.execute(
        "ALTER TABLE deals "
        "ADD CONSTRAINT valid_deal_status "
        "CHECK (status IN ('negotiation', 'contract_signing', 'deposit', 'legal_check', 'payment', 'closed', 'cancelled'))"
    )
    op.execute(
        "ALTER TABLE deals "
        "ADD CONSTRAINT valid_deal_source "
        "CHECK (source IN ('referral', 'site', 'direct', 'other'))"
    )

    # deal_participants
    op.execute(
        "ALTER TABLE deal_participants "
        "ADD CONSTRAINT valid_participant_role "
        "CHECK (role IN ('buyer', 'seller', 'tenant', 'landlord', 'agent', 'witness'))"
    )

    # documents
    op.execute(
        "ALTER TABLE documents "
        "ADD CONSTRAINT valid_document_type "
        "CHECK (document_type IN ('contract', 'passport', 'extract', 'deed', 'receipt', 'statement', 'photo', 'video', 'report', 'other'))"
    )
    op.execute(
        "ALTER TABLE documents "
        "ADD CONSTRAINT valid_document_status "
        "CHECK (status IN ('pending', 'received', 'verified', 'expired', 'rejected'))"
    )

    # communications
    op.execute(
        "ALTER TABLE communications "
        "ADD CONSTRAINT valid_communication_type "
        "CHECK (communication_type IN ('call', 'email', 'telegram', 'whatsapp', 'meeting', 'site_message', 'note'))"
    )
    op.execute(
        "ALTER TABLE communications "
        "ADD CONSTRAINT valid_direction "
        "CHECK (direction IN ('incoming', 'outgoing'))"
    )

    # tasks
    op.execute(
        "ALTER TABLE tasks "
        "ADD CONSTRAINT valid_task_status "
        "CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))"
    )
    op.execute(
        "ALTER TABLE tasks "
        "ADD CONSTRAINT valid_priority "
        "CHECK (priority IN ('low', 'medium', 'high', 'critical'))"
    )
    op.execute(
        "ALTER TABLE tasks "
        "ADD CONSTRAINT valid_task_type "
        "CHECK (task_type IN ('other', 'call', 'email', 'meeting', 'inspection', 'contract', 'payment'))"
    )

    # ── Indexes ────────────────────────────────────────────────
    # roles
    op.create_index("idx_roles_name", "roles", ["name"])
    op.create_index("idx_roles_is_system", "roles", ["is_system"])

    # users
    op.create_index("idx_users_role", "users", ["role_id"])
    op.create_index("idx_users_status", "users", ["status"])
    op.create_index("idx_users_telegram_id", "users", ["telegram_id"])
    op.create_index("idx_users_phone", "users", ["phone"])
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_created_at", "users", ["created_at"])

    # clients
    op.create_index("idx_clients_type_status", "clients", ["type", "status"])
    op.create_index("idx_clients_source", "clients", ["source"])
    op.create_index("idx_clients_telegram_id", "clients", ["telegram_id"])
    op.create_index("idx_clients_phone", "clients", ["phone"])
    op.create_index("idx_clients_created_at", "clients", ["created_at"])

    # client_contacts
    op.create_index("idx_client_contacts_client", "client_contacts", ["client_id"])
    op.create_index("idx_client_contacts_is_primary", "client_contacts", ["is_primary"])

    # properties
    op.create_index("idx_properties_status_deal", "properties", ["status", "deal_type"])
    op.create_index("idx_properties_type", "properties", ["property_type"])
    op.create_index("idx_properties_owner", "properties", ["owner_id"])
    op.create_index("idx_properties_price", "properties", ["price"])
    op.create_index("idx_properties_area_total", "properties", ["area_total"])
    op.create_index("idx_properties_rooms", "properties", ["rooms"])
    op.create_index("idx_properties_created_at", "properties", ["created_at"])

    # deals
    op.create_index("idx_deals_status", "deals", ["status"])
    op.create_index("idx_deals_property", "deals", ["property_id"])
    op.create_index("idx_deals_dates", "deals", ["start_date", "closing_date"])
    op.create_index("idx_deals_created_at", "deals", ["created_at"])

    # deal_participants
    op.create_index("idx_deal_participants_deal", "deal_participants", ["deal_id"])
    op.create_index("idx_deal_participants_client", "deal_participants", ["client_id"])
    op.create_index("idx_deal_participants_role", "deal_participants", ["role"])

    # documents
    op.create_index("idx_documents_client", "documents", ["client_id"])
    op.create_index("idx_documents_property", "documents", ["property_id"])
    op.create_index("idx_documents_deal", "documents", ["deal_id"])
    op.create_index("idx_documents_type_status", "documents", ["document_type", "status"])
    op.create_index("idx_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_index("idx_documents_expiry_date", "documents", ["expiry_date"])

    # communications
    op.create_index("idx_communications_client", "communications", ["client_id"])
    op.create_index("idx_communications_deal", "communications", ["deal_id"])
    op.create_index("idx_communications_assigned", "communications", ["assigned_to"])
    op.create_index("idx_communications_type_created", "communications", ["communication_type", "created_at"])
    op.create_index("idx_communications_is_important", "communications", ["is_important"])

    # tasks
    op.create_index("idx_tasks_assigned_status", "tasks", ["assigned_to", "status"])
    op.create_index("idx_tasks_due", "tasks", ["due_date"])
    op.create_index("idx_tasks_client", "tasks", ["client_id"])
    op.create_index("idx_tasks_deal", "tasks", ["deal_id"])
    op.create_index("idx_tasks_property", "tasks", ["property_id"])
    op.create_index("idx_tasks_priority", "tasks", ["priority"])
    op.create_index("idx_tasks_created_at", "tasks", ["created_at"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("tasks")
    op.drop_table("communications")
    op.drop_table("documents")
    op.drop_table("deal_participants")
    op.drop_table("deals")
    op.drop_table("properties")
    op.drop_table("client_contacts")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("roles")
