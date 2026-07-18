"""add_deal_operations: Playbooks, SLA, Timeline, Stakeholders, Validation, Health, Actions, Audit.

Revision ID: 020
Revises: 019_add_regulatory_intelligence
Create Date: 2026-06-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020_add_deal_operations"
down_revision: str | None = "019_add_regulatory_intelligence"


def upgrade() -> None:
    # deal_playbooks
    op.create_table("deal_playbooks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("deal_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("code"))
    op.create_index("ix_deal_playbooks_code", "deal_playbooks", ["code"])
    op.create_index("ix_deal_playbooks_deal_type", "deal_playbooks", ["deal_type"])

    # deal_playbook_stages
    op.create_table("deal_playbook_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("playbook_id", sa.UUID(), nullable=False),
        sa.Column("stage_key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sla_days", sa.Integer(), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["playbook_id"], ["deal_playbooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("playbook_id", "stage_key", name="uq_playbook_stage"))
    op.create_index("ix_deal_playbook_stages_playbook_id", "deal_playbook_stages", ["playbook_id"])

    # deal_playbook_checkpoints
    op.create_table("deal_playbook_checkpoints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("checkpoint_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("regulation_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["deal_playbook_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["regulation_id"], ["regulations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_playbook_checkpoints_stage_id", "deal_playbook_checkpoints", ["stage_id"])

    # deal_slas
    op.create_table("deal_slas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("stage_key", sa.String(50), nullable=False),
        sa.Column("sla_type", sa.String(30), server_default="stage", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_slas_deal_id", "deal_slas", ["deal_id"])
    op.create_index("ix_deal_slas_stage_key", "deal_slas", ["stage_key"])

    # deal_timeline_events
    op.create_table("deal_timeline_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source_component", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_timeline_events_deal_id", "deal_timeline_events", ["deal_id"])
    op.create_index("ix_deal_timeline_events_event_type", "deal_timeline_events", ["event_type"])
    op.create_index("ix_deal_timeline_events_created_at", "deal_timeline_events", ["created_at"])

    # stakeholders
    op.create_table("stakeholders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("stakeholder_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("contact_info", postgresql.JSONB(), nullable=True),
        sa.Column("responsibilities", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("is_blocking", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_stakeholders_deal_id", "stakeholders", ["deal_id"])
    op.create_index("ix_stakeholders_stakeholder_type", "stakeholders", ["stakeholder_type"])

    # document_validations
    op.create_table("document_validations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("validation_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("validation_score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("issues", postgresql.JSONB(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_document_validations_document_id", "document_validations", ["document_id"])

    # deal_health_snapshots
    op.create_table("deal_health_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("compliance_score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("risk_score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("sla_score", sa.Float(), server_default=sa.text("100.0"), nullable=False),
        sa.Column("document_score", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("activity_score", sa.Float(), server_default=sa.text("100.0"), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_health_snapshots_deal_id", "deal_health_snapshots", ["deal_id"])

    # deal_actions
    op.create_table("deal_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(10), server_default="medium", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_actions_deal_id", "deal_actions", ["deal_id"])
    op.create_index("ix_deal_actions_action_type", "deal_actions", ["action_type"])

    # deal_operations_audits
    op.create_table("deal_operations_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_deal_operations_audits_deal_id", "deal_operations_audits", ["deal_id"])
    op.create_index("ix_deal_operations_audits_operation_type", "deal_operations_audits", ["operation_type"])
    op.create_index("ix_deal_operations_audits_correlation_id", "deal_operations_audits", ["correlation_id"])

    # Seed playbooks
    from uuid import uuid4
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    playbooks = [
        ("residential-sale", "Продажа квартиры", "SALE_APARTMENT",
         [("lead", "Лид", 1, 3), ("inspection", "Осмотр", 2, 5), ("negotiation", "Переговоры", 3, 7),
          ("preparation", "Подготовка документов", 4, 14), ("signing", "Подписание", 5, 3), ("registration", "Регистрация", 6, 14), ("closing", "Закрытие", 7, 3)]),
        ("mortgage", "Ипотечная сделка", "MORTGAGE",
         [("lead", "Лид", 1, 3), ("bank_approval", "Одобрение банка", 2, 14), ("inspection", "Осмотр", 3, 5),
          ("preparation", "Подготовка", 4, 14), ("signing", "Подписание", 5, 3), ("registration", "Регистрация", 6, 14), ("closing", "Закрытие", 7, 3)]),
        ("new-building", "Новостройка", "SALE_APARTMENT",
         [("lead", "Лид", 1, 3), ("reservation", "Бронирование", 2, 3), ("contract", "Договор ДДУ", 3, 14),
          ("payment", "Оплата", 4, 30), ("acceptance", "Приёмка", 5, 7), ("registration", "Регистрация", 6, 30), ("closing", "Закрытие", 7, 3)]),
        ("commercial", "Коммерческая недвижимость", "SALE_APARTMENT",
         [("lead", "Лид", 1, 5), ("due_diligence", "Due Diligence", 2, 30), ("negotiation", "Переговоры", 3, 14),
          ("preparation", "Подготовка", 4, 21), ("signing", "Подписание", 5, 7), ("registration", "Регистрация", 6, 30), ("closing", "Закрытие", 7, 7)]),
        ("rental", "Аренда", "RENT",
         [("lead", "Лид", 1, 2), ("inspection", "Осмотр", 2, 3), ("negotiation", "Переговоры", 3, 3),
          ("preparation", "Договор", 4, 5), ("signing", "Подписание", 5, 2), ("move_in", "Заезд", 6, 3)]),
    ]
    for code, name, dt, stages in playbooks:
        pb_id = str(uuid4())
        op.execute(f"INSERT INTO deal_playbooks (id, code, name, deal_type, version, is_active) VALUES ('{pb_id}', '{code}', '{name}', '{dt}', '1.0', true)")
        for i, (sk, sn, seq, sla) in enumerate(stages):
            st_id = str(uuid4())
            op.execute(f"INSERT INTO deal_playbook_stages (id, playbook_id, stage_key, name, sequence, sla_days) VALUES ('{st_id}', '{pb_id}', '{sk}', '{sn}', {seq}, {sla})")


def downgrade() -> None:
    op.drop_table("deal_operations_audits")
    op.drop_table("deal_actions")
    op.drop_table("deal_health_snapshots")
    op.drop_table("document_validations")
    op.drop_table("stakeholders")
    op.drop_table("deal_timeline_events")
    op.drop_table("deal_slas")
    op.drop_table("deal_playbook_checkpoints")
    op.drop_table("deal_playbook_stages")
    op.drop_table("deal_playbooks")
