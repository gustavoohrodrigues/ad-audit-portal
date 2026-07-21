"""collection_checkpoints.last_event_record_id -> BIGINT.

Revision ID: 0008_ckpt_bigint
Revises: 0007_event_bigint
Create Date: 2026-07-21

Idempotente: só altera se ainda for 'integer'.
"""
from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0008_ckpt_bigint"
down_revision = "0007_event_bigint"
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
    if "bigint" not in _column_type("collection_checkpoints", "last_event_record_id"):
        op.execute(
            "ALTER TABLE collection_checkpoints "
            "ALTER COLUMN last_event_record_id TYPE BIGINT"
        )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE collection_checkpoints "
        "ALTER COLUMN last_event_record_id TYPE INTEGER"
    )
