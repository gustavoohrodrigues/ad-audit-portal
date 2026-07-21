"""Fase 1: histórico, notificações, watchlists, AS-REP flag e novos Event IDs.

Revision ID: 0003_analytics
Revises: 0002_mfa_pwd
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003_analytics"
down_revision = "0002_mfa_pwd"
branch_labels = None
depends_on = None

_NEW_EVENT_TYPES = [
    "kerberos_tgt_request", "kerberos_service_ticket", "kerberos_ticket_renewed",
    "kerberos_service_ticket_failed", "explicit_credential_logon",
    "special_privileges_assigned", "service_installed",
]


def upgrade() -> None:
    # 1) flag AS-REP roasting
    op.add_column(
        "ad_users",
        sa.Column("dont_require_preauth", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # 2) novos valores no enum eventtype (PG16 permite ADD VALUE em transação)
    for val in _NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE eventtype ADD VALUE IF NOT EXISTS '{val}'")

    # 3) histórico
    op.create_table(
        "security_score_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(), nullable=False),
        sa.Column("factors", JSONB(), nullable=True),
        sa.Column("computed_from", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_score_hist_day", "security_score_history", ["snapshot_date"], unique=True)

    op.create_table(
        "posture_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("counts", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_posture_hist_day", "posture_history", ["snapshot_date"], unique=True)

    # 4) notificações
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("requested_by", sa.String(), nullable=True),
        sa.Column("requester_role", sa.String(), nullable=True),
        sa.Column("justification", sa.String(), nullable=True),
        sa.Column("ticket_reference", sa.String(), nullable=True),
        sa.Column("context", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notif_created", "notification_deliveries", ["created_at"])
    op.create_index("ix_notif_corr", "notification_deliveries", ["correlation_id"])

    # 5) watchlists
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_watchlists_name", "watchlists", ["name"])
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_ref", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("added_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_watchlist_items_wl", "watchlist_items", ["watchlist_id"])
    op.create_index(
        "uq_watch_item", "watchlist_items",
        ["watchlist_id", "entity_type", "entity_ref"], unique=True,
    )


def downgrade() -> None:
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("notification_deliveries")
    op.drop_table("posture_history")
    op.drop_table("security_score_history")
    op.drop_column("ad_users", "dont_require_preauth")
    # valores de enum não são removidos (ALTER TYPE ... DROP VALUE não é suportado)
