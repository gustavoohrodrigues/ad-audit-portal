"""Portal de webhooks de chat (Google Chat) + central de mensagens.

Revision ID: 0006_chat_webhooks
Revises: 0005_perf_indexes
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_chat_webhooks"
down_revision = "0005_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="google_chat"),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chat_webhooks_name", "chat_webhooks", ["name"])


def downgrade() -> None:
    op.drop_index("ix_chat_webhooks_name", table_name="chat_webhooks")
    op.drop_table("chat_webhooks")
