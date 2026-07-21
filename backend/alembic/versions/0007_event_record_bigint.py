"""normalized_events.event_record_id -> BIGINT (EventRecordID do Windows é grande).

Revision ID: 0007_event_bigint
Revises: 0006_chat_webhooks
Create Date: 2026-07-21

Idempotente: só altera se a coluna ainda for 'integer' (em deploy novo o
create_all já cria como BIGINT).
"""
from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0007_event_bigint"
down_revision = "0006_chat_webhooks"
branch_labels = None
depends_on = None


def _column_type(table: str, column: str) -> str:
    try:
        for c in inspect(op.get_bind()).get_columns(table):
            if c["name"] == column:
                return str(c["type"]).lower()
    except Exception:  # noqa: BLE001
        pass
    return ""


def upgrade() -> None:
    if "bigint" not in _column_type("normalized_events", "event_record_id"):
        op.execute(
            "ALTER TABLE normalized_events "
            "ALTER COLUMN event_record_id TYPE BIGINT"
        )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE normalized_events ALTER COLUMN event_record_id TYPE INTEGER"
    )
