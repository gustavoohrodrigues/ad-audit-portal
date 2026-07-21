"""Fase 2: playbook de bloqueio + checkpoint uSNChanged (sync incremental).

Revision ID: 0004_playbook_usn
Revises: 0003_analytics
Create Date: 2026-07-21

Idempotente (ver nota na 0002).
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004_playbook_usn"
down_revision = "0003_analytics"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))
    except Exception:  # noqa: BLE001
        return False


def _has_table(table: str) -> bool:
    try:
        return inspect(op.get_bind()).has_table(table)
    except Exception:  # noqa: BLE001
        return False


def upgrade() -> None:
    if not _has_column("lockout_investigations", "playbook_state"):
        op.add_column("lockout_investigations", sa.Column("playbook_state", JSONB(), nullable=True))

    if not _has_table("ad_sync_checkpoints"):
        op.create_table(
            "ad_sync_checkpoints",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("highest_usn", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_incremental_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_ad_sync_source", "ad_sync_checkpoints", ["source"], unique=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ad_sync_checkpoints")
    op.execute("ALTER TABLE lockout_investigations DROP COLUMN IF EXISTS playbook_state")
