"""Schema inicial — cria todas as tabelas a partir do metadata do SQLModel.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-20

Esta migração de bootstrap materializa o modelo declarado em app.models como
fonte única de verdade. Migrações subsequentes devem usar operações explícitas
(op.add_column, etc.) geradas por `alembic revision --autogenerate`.
"""
from __future__ import annotations

from sqlmodel import SQLModel

from alembic import op

# importa todos os modelos para popular o metadata
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
