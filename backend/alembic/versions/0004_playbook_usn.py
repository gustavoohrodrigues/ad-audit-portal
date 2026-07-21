"""Fase 2: playbook de bloqueio + checkpoint uSNChanged (sync incremental).

Revision ID: 0004_playbook_usn
Revises: 0003_analytics
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004_playbook_usn"
down_revision = "0003_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lockout_investigations",
        sa.Column("playbook_state", JSONB(), nullable=True),
    )
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
    op.drop_index("ix_ad_sync_source", table_name="ad_sync_checkpoints")
    op.drop_table("ad_sync_checkpoints")
    op.drop_column("lockout_investigations", "playbook_state")
