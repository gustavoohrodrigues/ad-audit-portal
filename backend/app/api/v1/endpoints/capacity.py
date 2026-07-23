"""Capacidade & Performance (admin): tamanho do banco, tabelas, Redis, filas.

Somente leitura, dados operacionais. Não expõe conteúdo de eventos nem PII.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, require_role
from app.core.redis_client import redis_client
from app.database import get_session
from app.models.enums import Role

router = APIRouter(prefix="/admin/capacity", tags=["capacity"])
settings = get_settings()

# filas Celery (default broker db) — profundidade via LLEN das listas
CELERY_QUEUES = ["celery", "ingestion_high", "ingestion_default", "correlation",
                 "alerts", "reports", "sync", "maintenance", "low_priority"]


@router.get("")
async def capacity(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    # --- PostgreSQL ---
    db_size = (
        await session.execute(text("SELECT pg_database_size(current_database())"))
    ).scalar_one()

    top_tables = (
        await session.execute(text(
            """
            SELECT c.relname AS table_name,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   COALESCE(s.n_live_tup, 0) AS row_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relkind = 'r' AND n.nspname = 'public'
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 12
            """
        ))
    ).all()

    # contagens das tabelas centrais via ESTIMATIVA do planner (n_live_tup) —
    # evita count(*) com seq scan na tabela de eventos a cada refresh (30s).
    _tables = ["normalized_events", "ad_users", "ad_groups", "ad_computers",
               "alerts", "lockout_investigations", "internal_audit_log",
               "notification_deliveries"]
    counts = {t: None for t in _tables}
    for r in (await session.execute(text(
        "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname = ANY(:t)"
    ), {"t": _tables})).all():
        counts[r[0]] = int(r[1])

    # --- Analytics de ingestão (taxa + distribuição por tipo, últimas 24h) ---
    async def _c(sql: str) -> int:
        return int((await session.execute(text(sql))).scalar_one() or 0)

    _base = "SELECT count(*) FROM normalized_events WHERE event_time_utc > (now() AT TIME ZONE 'UTC')"
    ingestion = {
        "events_1h": await _c(f"{_base} - interval '1 hour'"),
        "events_24h": await _c(f"{_base} - interval '24 hours'"),
        "events_7d": await _c(f"{_base} - interval '7 days'"),
        "by_type": [
            {"type": r[0], "count": int(r[1])}
            for r in (await session.execute(text(
                "SELECT event_type::text, count(*) FROM normalized_events "
                "WHERE event_time_utc > (now() AT TIME ZONE 'UTC') - interval '24 hours' "
                "GROUP BY event_type ORDER BY 2 DESC LIMIT 12"
            ))).all()
        ],
    }

    # índices possivelmente não usados (idx_scan = 0)
    unused_idx = (
        await session.execute(text(
            """
            SELECT relname AS table, indexrelname AS index, idx_scan AS scans
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            ORDER BY relname
            LIMIT 20
            """
        ))
    ).all()

    # --- Redis ---
    redis_info: dict = {}
    try:
        info = await redis_client.info()
        redis_info = {
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "evicted_keys": info.get("evicted_keys"),
            "uptime_days": round(info.get("uptime_in_seconds", 0) / 86400, 1),
        }
        db_keys = await redis_client.dbsize()
        redis_info["keys"] = db_keys
    except Exception:  # noqa: BLE001
        redis_info = {"error": "indisponível"}

    # --- Filas Celery (profundidade) ---
    queues = {}
    try:
        from redis import Redis  # broker é outro db; usa REDIS/broker URL

        broker = Redis.from_url(settings.celery_broker_url)
        for q in CELERY_QUEUES:
            try:
                queues[q] = broker.llen(q)
            except Exception:  # noqa: BLE001
                queues[q] = None
        broker.close()
    except Exception:  # noqa: BLE001
        queues = {}

    return {
        "database": {
            "size_bytes": db_size,
            "size_human": _human(db_size),
            "counts": counts,
            "top_tables": [
                {"table": r[0], "size_human": _human(r[1]), "rows": r[2]}
                for r in top_tables
            ],
            "unused_indexes": [
                {"table": r[0], "index": r[1]} for r in unused_idx
            ],
        },
        "redis": redis_info,
        "celery_queues": queues,
        "ingestion": ingestion,
        "config": {
            "sql_pool_size": settings.api_sql_pool_size,
            "sql_max_overflow": settings.api_sql_max_overflow,
            "cache_enabled": settings.cache_enabled,
            "partitioning_enabled": settings.feature_partitioning_enabled,
            "max_page_size": settings.api_max_page_size,
        },
    }


def _human(n: int | None) -> str:
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
