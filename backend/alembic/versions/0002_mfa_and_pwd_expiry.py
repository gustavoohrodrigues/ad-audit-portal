"""Adiciona MFA (user_mfa) e coluna ad_users.password_expires_at.

Revision ID: 0002_mfa_pwd
Revises: 0001_initial
Create Date: 2026-07-21

Idempotente: a migração de bootstrap 0001 usa create_all (que reflete os modelos
atuais), então em um deploy novo as tabelas/colunas já podem existir. Guardamos
cada operação com verificação de existência para reprodutibilidade.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002_mfa_pwd"
down_revision = "0001_initial"
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
    if not _has_column("ad_users", "password_expires_at"):
        op.add_column(
            "ad_users",
            sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_table("user_mfa"):
        op.create_table(
            "user_mfa",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sam_account_name", sa.String(), nullable=False),
            sa.Column("secret", sa.String(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("backup_codes", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_user_mfa_sam", "user_mfa", ["sam_account_name"], unique=True)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_mfa_sam")
    op.execute("DROP TABLE IF EXISTS user_mfa")
    op.execute("ALTER TABLE ad_users DROP COLUMN IF EXISTS password_expires_at")
