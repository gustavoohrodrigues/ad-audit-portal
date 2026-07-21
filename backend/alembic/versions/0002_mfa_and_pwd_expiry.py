"""Adiciona MFA (user_mfa) e coluna ad_users.password_expires_at.

Revision ID: 0002_mfa_pwd
Revises: 0001_initial
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002_mfa_pwd"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # coluna de expiração de senha (idempotente)
    op.add_column(
        "ad_users",
        sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # tabela de MFA
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
    op.drop_index("ix_user_mfa_sam", table_name="user_mfa")
    op.drop_table("user_mfa")
    op.drop_column("ad_users", "password_expires_at")
