"""Performance de eventos: autovacuum agressivo, índice BRIN e limpeza de índices.

Revision ID: 0010_events_perf
Revises: 0009_chat_alerts
Create Date: 2026-07-23

- Autovacuum agressivo em normalized_events (evita bloat de linhas mortas em
  tabela de alto churn, principal causa de lentidão/travamento).
- Índice BRIN em event_time_utc: minúsculo e eficiente para varreduras por
  período numa tabela append-only enorme.
- Remove ix_event_upn (baixo valor, encarece cada INSERT).

Idempotente.
"""
from __future__ import annotations

from alembic import op

revision = "0010_events_perf"
down_revision = "0009_chat_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Autovacuum/analyze agressivos para conter bloat na tabela de eventos.
    op.execute(
        """
        ALTER TABLE normalized_events SET (
            autovacuum_vacuum_scale_factor = 0.02,
            autovacuum_analyze_scale_factor = 0.01,
            autovacuum_vacuum_threshold = 5000,
            autovacuum_analyze_threshold = 5000,
            autovacuum_vacuum_cost_limit = 2000
        )
        """
    )
    # BRIN é ideal para colunas temporais crescentes; ocupa poucos KB.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_event_time_brin "
        "ON normalized_events USING brin (event_time_utc)"
    )
    # Remove índice de baixo valor que só encarece a escrita.
    op.execute("DROP INDEX IF EXISTS ix_event_upn")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_event_time_brin")
    op.execute(
        "ALTER TABLE normalized_events RESET ("
        "autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor, "
        "autovacuum_vacuum_threshold, autovacuum_analyze_threshold, "
        "autovacuum_vacuum_cost_limit)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_event_upn ON normalized_events (target_upn)"
    )
