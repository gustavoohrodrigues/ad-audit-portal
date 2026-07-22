"""Manutenção e limpeza do banco — retenção, purge em lotes e VACUUM.

Evita sobrecarga do PostgreSQL removendo dados além da política de retenção,
limpando o JSON bruto antigo (mantendo o evento normalizado) e recuperando
espaço em disco. Purges são feitos em LOTES para não travar a base.

Para reduzir o tamanho FÍSICO do arquivo (não só marcar espaço reutilizável),
use `full=True` (VACUUM FULL) — reescreve as tabelas e devolve espaço ao SO,
com lock exclusivo breve. Reduza `raw_days` para esvaziar o JSON bruto de
eventos recentes e liberar a maior parte do volume.

Somente leitura em relação ao AD.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import engine

logger = get_logger(__name__)
settings = get_settings()

# Tabelas de maior rotatividade — alvo do VACUUM e da medição de espaço.
_HOT_TABLES = ("normalized_events", "internal_audit_log", "notification_deliveries")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _db_size(session: AsyncSession) -> int:
    r = await session.execute(text("SELECT pg_database_size(current_database())"))
    return int(r.scalar() or 0)


async def _batched_delete(session: AsyncSession, table: str, where: str, params: dict,
                          batch: int = 5000, max_loops: int = 2000) -> int:
    """Deleta em lotes usando ctid (eficiente e sem lock longo)."""
    total = 0
    for _ in range(max_loops):
        res = await session.execute(
            text(
                f"DELETE FROM {table} WHERE ctid IN "
                f"(SELECT ctid FROM {table} WHERE {where} LIMIT {batch})"
            ),
            params,
        )
        await session.commit()
        n = res.rowcount or 0
        total += n
        if n < batch:
            break
    return total


async def run_cleanup(session: AsyncSession, vacuum: bool | None = None,
                      full: bool = False, raw_days: int | None = None) -> dict:
    """Executa a limpeza/retenção. Retorna estatísticas por etapa.

    - vacuum: None usa a config; True/False força. `full=True` implica vacuum.
    - full: VACUUM FULL (encolhe o arquivo em disco; lock exclusivo breve).
    - raw_days: sobrepõe a retenção do JSON bruto para esta execução (permite
      esvaziar o JSON de eventos recentes e liberar volume sem editar o .env).
    """
    now = _now()
    do_vacuum = (settings.maintenance_vacuum_enabled if vacuum is None else vacuum) or full
    raw_horizon = settings.event_raw_retention_days if raw_days is None else max(0, int(raw_days))
    stats: dict[str, int | str] = {}
    size_before = await _db_size(session)

    # 1) esvazia o JSON bruto além do horizonte (preserva o evento normalizado)
    raw_cut = now - timedelta(days=raw_horizon)
    r = await session.execute(
        text(
            "UPDATE normalized_events SET raw_event_json = '{}'::jsonb "
            "WHERE event_time_utc < :cut AND raw_event_json <> '{}'::jsonb"
        ),
        {"cut": raw_cut},
    )
    await session.commit()
    stats["raw_json_cleared"] = r.rowcount or 0
    stats["raw_horizon_days"] = raw_horizon

    # 2) eventos além da retenção total (em lotes)
    evt_cut = now - timedelta(days=settings.event_retention_days)
    stats["events_deleted"] = await _batched_delete(
        session, "normalized_events", "event_time_utc < :cut", {"cut": evt_cut}
    )

    # 3) auditoria interna antiga (em lotes)
    audit_cut = now - timedelta(days=settings.audit_log_retention_days)
    stats["audit_deleted"] = await _batched_delete(
        session, "internal_audit_log", "created_at < :cut", {"cut": audit_cut}
    )

    # 4) histórico de notificações antigo
    notif_cut = now - timedelta(days=settings.notification_retention_days)
    stats["notifications_deleted"] = await _batched_delete(
        session, "notification_deliveries", "created_at < :cut", {"cut": notif_cut}
    )

    # 5) exportações registradas antigas
    stats["exports_deleted"] = await _batched_delete(
        session, "report_exports", "created_at < :cut",
        {"cut": now - timedelta(days=settings.audit_log_retention_days)}
    )

    # 6) registra a execução na política de retenção
    for dtype, days in (
        ("events", settings.event_retention_days),
        ("raw_events", raw_horizon),
        ("audit", settings.audit_log_retention_days),
        ("notifications", settings.notification_retention_days),
    ):
        await session.execute(
            text(
                "INSERT INTO retention_policies (data_type, retention_days, enabled, "
                "last_purge_at, updated_at) VALUES (:dt,:days,true,:now,:now) "
                "ON CONFLICT (data_type) DO UPDATE SET retention_days=EXCLUDED.retention_days, "
                "last_purge_at=EXCLUDED.last_purge_at, updated_at=EXCLUDED.updated_at"
            ),
            {"dt": dtype, "days": days, "now": now},
        )
    await session.commit()

    # 7) VACUUM — recupera espaço. FULL encolhe o arquivo (lock exclusivo breve).
    if do_vacuum:
        cmd = "VACUUM (FULL, ANALYZE)" if full else "VACUUM (ANALYZE)"
        try:
            async with engine.connect() as conn:
                conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                # VACUUM pode demorar: remove timeouts nesta sessão.
                await conn.execute(text("SET statement_timeout = 0"))
                await conn.execute(text("SET lock_timeout = 0"))
                for tbl in _HOT_TABLES:
                    await conn.execute(text(f"{cmd} {tbl}"))
            stats["vacuum"] = 1
            stats["vacuum_full"] = 1 if full else 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("VACUUM falhou: %s", exc)
            stats["vacuum"] = 0
            stats["vacuum_error"] = str(exc)[:300]

    size_after = await _db_size(session)
    stats["size_before"] = size_before
    stats["size_after"] = size_after
    stats["bytes_reclaimed"] = max(0, size_before - size_after)

    logger.info("Limpeza do banco concluída: %s", stats)
    return stats


async def maintenance_status(session: AsyncSession) -> dict:
    """Tamanhos das tabelas centrais + políticas de retenção configuradas."""
    sizes = (
        await session.execute(text(
            "SELECT c.relname AS t, pg_total_relation_size(c.oid) AS bytes, "
            "COALESCE(s.n_live_tup,0) AS rows, COALESCE(s.n_dead_tup,0) AS dead "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "LEFT JOIN pg_stat_user_tables s ON s.relid=c.oid "
            "WHERE c.relkind='r' AND n.nspname='public' "
            "ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 15"
        ))
    ).all()
    policies = (
        await session.execute(text(
            "SELECT data_type, retention_days, last_purge_at FROM retention_policies"
        ))
    ).all()
    return {
        "database_bytes": await _db_size(session),
        "tables": [
            {"table": r[0], "bytes": r[1], "rows": r[2], "dead_rows": r[3]} for r in sizes
        ],
        "policies": [
            {"data_type": p[0], "retention_days": p[1], "last_purge_at": p[2]} for p in policies
        ],
        "config": {
            "event_retention_days": settings.event_retention_days,
            "raw_retention_days": settings.event_raw_retention_days,
            "audit_retention_days": settings.audit_log_retention_days,
            "notification_retention_days": settings.notification_retention_days,
            "vacuum_enabled": settings.maintenance_vacuum_enabled,
        },
    }
