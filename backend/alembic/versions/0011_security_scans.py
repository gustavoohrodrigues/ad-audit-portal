"""security_scans — histórico de varreduras de segurança (nmap).

Revision ID: 0011_security_scans
Revises: 0010_events_perf
Create Date: 2026-07-23

Idempotente.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0011_security_scans"
down_revision = "0010_events_perf"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    try:
        return name in inspect(op.get_bind()).get_table_names()
    except Exception:  # noqa: BLE001
        return False


def upgrade() -> None:
    if _has_table("security_scans"):
        return
    op.create_table(
        "security_scans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("target", sa.String, nullable=False),
        sa.Column("profile", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String, nullable=True),
        sa.Column("hosts_up", sa.Integer, nullable=False, server_default="0"),
        sa.Column("open_ports", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("result", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_scan_created", "security_scans", ["created_at"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS security_scans")
