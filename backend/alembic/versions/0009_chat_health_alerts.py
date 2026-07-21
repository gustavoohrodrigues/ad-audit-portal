"""chat_webhooks.health_alerts (recebe alertas automáticos de saúde).

Revision ID: 0009_chat_alerts
Revises: 0008_ckpt_bigint
Create Date: 2026-07-22

Idempotente.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0009_chat_alerts"
down_revision = "0008_ckpt_bigint"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))
    except Exception:  # noqa: BLE001
        return False


def upgrade() -> None:
    if not _has_column("chat_webhooks", "health_alerts"):
        op.add_column(
            "chat_webhooks",
            sa.Column("health_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    op.execute("ALTER TABLE chat_webhooks DROP COLUMN IF EXISTS health_alerts")
