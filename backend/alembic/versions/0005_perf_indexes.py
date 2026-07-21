"""Fase 1: índices compostos e parciais para performance de consultas.

Revision ID: 0005_perf_indexes
Revises: 0004_playbook_usn
Create Date: 2026-07-21

Índices adicionais em normalized_events para os padrões de consulta reais
(dashboard, timeline por entidade, rankings, correlação). Não destrutivo.
"""
from __future__ import annotations

from alembic import op

revision = "0005_perf_indexes"
down_revision = "0004_playbook_usn"
branch_labels = None
depends_on = None

# (nome, definição SQL) — CREATE INDEX IF NOT EXISTS para idempotência
_INDEXES = [
    ("ix_ev_time_eventid", "normalized_events (event_time_utc DESC, event_id)"),
    ("ix_ev_sid_time", "normalized_events (target_sid, event_time_utc DESC)"),
    ("ix_ev_upn_time", "normalized_events (target_upn, event_time_utc DESC)"),
    ("ix_ev_srcip_time", "normalized_events (source_ip, event_time_utc DESC)"),
    ("ix_ev_risk_time", "normalized_events (risk_score DESC, event_time_utc DESC)"),
    ("ix_ev_sev_time", "normalized_events (severity, event_time_utc DESC)"),
    ("ix_ev_collector_ing", "normalized_events (collector_source, ingested_at DESC)"),
]

# índices parciais (só linhas relevantes) — reduzem tamanho e aceleram filtros
_PARTIAL = [
    ("ix_ev_lockouts", "normalized_events (target_username, event_time_utc DESC)",
     "event_type = 'account_lockout'"),
    ("ix_ev_failed_logon", "normalized_events (event_time_utc DESC)",
     "event_type IN ('failed_logon','kerberos_preauth_failed','ntlm_validation')"),
    ("ix_ev_privileged", "normalized_events (event_time_utc DESC)",
     "is_privileged_target = true"),
    ("ix_ev_critical", "normalized_events (event_time_utc DESC)",
     "risk_score >= 75"),
]


def upgrade() -> None:
    for name, definition in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {definition}")
    for name, definition, where in _PARTIAL:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {definition} WHERE {where}")


def downgrade() -> None:
    for name, _ in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    for name, _, _ in _PARTIAL:
        op.execute(f"DROP INDEX IF EXISTS {name}")
