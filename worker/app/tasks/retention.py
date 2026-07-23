"""Retenção e expurgo automático (LGPD / política configurável).

- Eventos de RUÍDO (ruído de autenticação de alto volume) são removidos após
  EVENT_NOISE_RETENTION_DAYS — este é o principal freio ao crescimento do banco.
- Demais eventos são removidos após EVENT_RETENTION_DAYS.
- JSON bruto (raw_event_json) é esvaziado após EVENT_RAW_RETENTION_DAYS,
  preservando os campos normalizados por mais tempo.
- Logs de auditoria/notificações além da retenção são removidos.

Todos os DELETEs são feitos em LOTES (ctid) para não travar a base.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.celery_app import celery_app
from app.config import config
from app.db import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _batched_delete(s, table: str, where: str, params: dict,
                    batch: int = 5000, max_loops: int = 4000) -> int:
    """DELETE em lotes via ctid — sem lock longo em tabelas grandes."""
    total = 0
    for _ in range(max_loops):
        r = s.execute(
            text(
                f"DELETE FROM {table} WHERE ctid IN "
                f"(SELECT ctid FROM {table} WHERE {where} LIMIT {batch})"
            ),
            params,
        )
        s.commit()
        n = r.rowcount or 0
        total += n
        if n < batch:
            break
    return total


@celery_app.task(name="app.tasks.retention.apply_retention")
def apply_retention() -> dict:
    now = _utcnow()
    result = {}
    noise_types = [t.strip() for t in config.event_noise_types.split(",") if t.strip()]
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
        s.commit()
        result["raw_cleared"] = r.rowcount

        # 2) remove eventos de RUÍDO (alto volume) mais cedo — em lotes
        if noise_types:
            noise_cut = now - timedelta(days=config.event_noise_retention_days)
            result["noise_deleted"] = _batched_delete(
                s, "normalized_events",
                "event_time_utc < :cut AND event_type::text = ANY(:types)",
                {"cut": noise_cut, "types": noise_types},
            )

        # 3) remove os demais eventos além da retenção total — em lotes
        evt_cut = now - timedelta(days=config.event_retention_days)
        result["events_deleted"] = _batched_delete(
            s, "normalized_events", "event_time_utc < :cut", {"cut": evt_cut},
        )

        # 4) remove auditoria interna antiga
        audit_cut = now - timedelta(days=config.audit_retention_days)
        result["audit_deleted"] = _batched_delete(
            s, "internal_audit_log", "created_at < :cut", {"cut": audit_cut},
        )

        # 5) remove histórico de notificações antigo
        notif_cut = now - timedelta(days=config.notification_retention_days)
        try:
            result["notifications_deleted"] = _batched_delete(
                s, "notification_deliveries", "created_at < :cut", {"cut": notif_cut},
            )
        except Exception:  # tabela pode não existir em versões antigas
            pass

        # 6) registra a execução da política
        for dtype, days in (
            ("events", config.event_retention_days),
            ("noise_events", config.event_noise_retention_days),
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
