"""Retenção e expurgo automático (LGPD / política configurável).

- Eventos além de EVENT_RETENTION_DAYS são removidos.
- JSON bruto (raw_event_json) é esvaziado após EVENT_RAW_RETENTION_DAYS,
  preservando os campos normalizados por mais tempo.
- Logs de auditoria interna além de AUDIT_LOG_RETENTION_DAYS são removidos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.celery_app import celery_app
from app.config import config
from app.db import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.retention.apply_retention")
def apply_retention() -> dict:
    now = _utcnow()
    result = {}
    with session_scope() as s:
        # 1) purga JSON bruto antigo (mantém evento normalizado)
        raw_cut = now - timedelta(days=config.raw_retention_days)
        r = s.execute(
            text(
                """
                UPDATE normalized_events
                SET raw_event_json = '{}'::jsonb
                WHERE event_time_utc < :cut AND raw_event_json <> '{}'::jsonb
                """
            ),
            {"cut": raw_cut},
        )
        result["raw_cleared"] = r.rowcount

        # 2) remove eventos além da retenção total
        evt_cut = now - timedelta(days=config.event_retention_days)
        r = s.execute(
            text("DELETE FROM normalized_events WHERE event_time_utc < :cut"),
            {"cut": evt_cut},
        )
        result["events_deleted"] = r.rowcount

        # 3) remove auditoria interna antiga
        audit_cut = now - timedelta(days=config.audit_retention_days)
        r = s.execute(
            text("DELETE FROM internal_audit_log WHERE created_at < :cut"),
            {"cut": audit_cut},
        )
        result["audit_deleted"] = r.rowcount

        # 4) registra a execução da política
        for dtype, days in (
            ("events", config.event_retention_days),
            ("raw_events", config.raw_retention_days),
            ("audit", config.audit_retention_days),
        ):
            s.execute(
                text(
                    """
                    INSERT INTO retention_policies (data_type, retention_days, enabled,
                        last_purge_at, updated_at)
                    VALUES (:dt,:days,true,:now,:now)
                    ON CONFLICT (data_type) DO UPDATE SET
                        retention_days=EXCLUDED.retention_days,
                        last_purge_at=EXCLUDED.last_purge_at,
                        updated_at=EXCLUDED.updated_at
                    """
                ),
                {"dt": dtype, "days": days, "now": now},
            )
    return result
