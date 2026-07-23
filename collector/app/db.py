"""Persistência do collector: inserção idempotente + checkpoint por fonte.

A deduplicação usa o índice único (domain_controller, event_record_id, event_id)
via ``ON CONFLICT DO NOTHING`` — garante que reentregas de eventos (comuns em
WEF) não gerem duplicatas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import config

engine = create_async_engine(config.database_url, pool_pre_ping=True)

# Colunas (ordem fixa) — usada para montar params uniformes para executemany.
_COLUMNS = (
    "event_time_utc", "ingested_at", "event_record_id", "event_id", "event_type",
    "severity", "risk_score", "domain", "domain_controller", "target_username",
    "target_upn", "target_sid", "actor_username", "actor_domain", "actor_sid",
    "caller_computer", "source_host", "source_ip", "logon_id", "workstation_name",
    "authentication_package", "status_code", "failure_reason", "collector_source",
    "correlation_id", "raw_event_json", "is_privileged_target", "is_critical_account",
    "created_at", "updated_at",
)

# Sem RETURNING: permite executemany (uma ida ao banco por lote) em vez de uma
# ida por linha — elimina o gargalo/travamento de ingestão de alto volume.
_INSERT = text(
    """
    INSERT INTO normalized_events (
        event_time_utc, ingested_at, event_record_id, event_id, event_type,
        severity, risk_score, domain, domain_controller, target_username,
        target_upn, target_sid, actor_username, actor_domain, actor_sid,
        caller_computer, source_host, source_ip, logon_id, workstation_name,
        authentication_package, status_code, failure_reason, collector_source,
        correlation_id, raw_event_json, is_privileged_target, is_critical_account,
        created_at, updated_at
    ) VALUES (
        :event_time_utc, :ingested_at, :event_record_id, :event_id, :event_type,
        :severity, :risk_score, :domain, :domain_controller, :target_username,
        :target_upn, :target_sid, :actor_username, :actor_domain, :actor_sid,
        :caller_computer, :source_host, :source_ip, :logon_id, :workstation_name,
        :authentication_package, :status_code, :failure_reason, :collector_source,
        :correlation_id, CAST(:raw_event_json AS JSONB), :is_privileged_target,
        :is_critical_account, :created_at, :updated_at
    )
    ON CONFLICT (domain_controller, event_record_id, event_id) DO NOTHING
    """
)

_CHECKPOINT_UPSERT = text(
    """
    INSERT INTO collection_checkpoints (source, channel, last_event_record_id,
        last_event_time_utc, bookmark, updated_at)
    VALUES (:source, :channel, :rec_id, :evt_time, :bookmark, :updated_at)
    ON CONFLICT (source, channel) DO UPDATE SET
        last_event_record_id = GREATEST(
            COALESCE(collection_checkpoints.last_event_record_id, 0),
            EXCLUDED.last_event_record_id),
        last_event_time_utc = EXCLUDED.last_event_time_utc,
        bookmark = EXCLUDED.bookmark,
        updated_at = EXCLUDED.updated_at
    """
)

# Upsert: cria a fonte na primeira execução e acumula estatísticas depois, para
# que a tela "Pontos de Coleta" reflita o coletor real (não só o seed de demo).
_SOURCE_STATS = text(
    """
    INSERT INTO event_sources (name, connector_type, enabled, status,
        last_event_at, last_heartbeat_at, events_ingested, errors_count, updated_at)
    VALUES (:name, :ctype, true, :status, :last_event, :hb, :n, :err, :hb)
    ON CONFLICT (name) DO UPDATE SET
        events_ingested = event_sources.events_ingested + EXCLUDED.events_ingested,
        errors_count = event_sources.errors_count + EXCLUDED.errors_count,
        last_event_at = COALESCE(EXCLUDED.last_event_at, event_sources.last_event_at),
        last_heartbeat_at = EXCLUDED.last_heartbeat_at,
        status = EXCLUDED.status,
        connector_type = EXCLUDED.connector_type,
        updated_at = EXCLUDED.updated_at
    """
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_params(r: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Monta um dict com TODAS as colunas (chaves uniformes p/ executemany)."""
    import json

    p = {c: r.get(c) for c in _COLUMNS}
    p["ingested_at"] = now
    p["created_at"] = now
    p["updated_at"] = now
    p["severity"] = r.get("severity", "info")
    p["risk_score"] = r.get("risk_score", 0) or 0
    p["is_critical_account"] = r.get("is_critical_account", False)
    p["is_privileged_target"] = r.get("is_privileged_target", False)
    p["raw_event_json"] = json.dumps(r.get("raw_event_json") or {}, default=str)
    return p


async def insert_events(rows: list[dict[str, Any]]) -> int:
    """Insere eventos em UM único executemany por lote (dedup via ON CONFLICT).

    Retorna o número de linhas afetadas (aproxima os efetivamente gravados; com
    ON CONFLICT DO NOTHING, duplicatas não contam).
    """
    if not rows:
        return 0
    now = _now()
    params = [_row_params(r, now) for r in rows]
    async with engine.begin() as conn:
        result = await conn.execute(_INSERT, params)
    rc = result.rowcount
    return rc if isinstance(rc, int) and rc >= 0 else len(rows)


async def update_checkpoint(
    source: str, channel: str, rec_id: int | None, evt_time: datetime | None,
    bookmark: str | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            _CHECKPOINT_UPSERT,
            {
                "source": source,
                "channel": channel,
                "rec_id": rec_id or 0,
                "evt_time": evt_time,
                "bookmark": bookmark,
                "updated_at": _now(),
            },
        )


async def update_source_stats(
    name: str, n: int, errors: int, last_event: datetime | None, status: str
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            _SOURCE_STATS,
            {
                "name": name,
                "ctype": config.mode,
                "n": n,
                "err": errors,
                "last_event": last_event,
                "hb": _now(),
                "status": status,
            },
        )


async def get_checkpoint(source: str, channel: str = "Security") -> dict | None:
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT last_event_record_id, bookmark FROM collection_checkpoints "
                    "WHERE source=:s AND channel=:c"
                ),
                {"s": source, "c": channel},
            )
        ).first()
    return {"last_record_id": row[0], "bookmark": row[1]} if row else None
