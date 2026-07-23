"""Painel de Saúde & Alertas (estilo Ceph) e feed de notificações.

- GET  /monitoring/health         -> status geral + health checks
- GET  /monitoring/notifications  -> resumo para o sino (contagem + itens)
- POST /monitoring/checks/{id}/mute e /unmute (admin) -> silenciar check
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability, require_role
from app.core.redis_client import redis_client
from app.database import get_session
from app.models.enums import AlertStatus, Role
from app.models.ops import Alert, CollectionCheckpoint, EventSource
from app.services.health import evaluate

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_MUTED_KEY = "health:muted"


async def _muted() -> set[str]:
    return set(await redis_client.smembers(_MUTED_KEY))


@router.get("/health")
async def health_checks(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    return await evaluate(session, await _muted())


@router.get("/notifications")
async def notifications(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    """Resumo compacto para o sino: health checks ativos + alertas críticos abertos."""
    health = await evaluate(session, await _muted())
    active = [c for c in health["checks"] if not c["muted"] and c["severity"] != "ok"]

    open_alerts = (
        await session.execute(
            select(Alert).where(Alert.status == AlertStatus.open)
            .order_by(Alert.created_at.desc()).limit(10)
        )
    ).scalars().all()

    items = [
        {
            "kind": "health",
            "id": c["id"],
            "severity": c["severity"],
            "title": c["summary"],
            "link": c["link"],
        }
        for c in active
    ] + [
        {
            "kind": "alert",
            "id": f"alert:{a.id}",
            "severity": a.severity,
            "title": a.title,
            "link": "/alerts",
        }
        for a in open_alerts
    ]
    return {
        "status": health["status"],
        "count": len(items),
        "error": health["summary"]["error"],
        "warning": health["summary"]["warning"],
        "items": items[:15],
    }


@router.post("/checks/{check_id}/mute")
async def mute_check(
    check_id: str,
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    await redis_client.sadd(_MUTED_KEY, check_id)
    return {"muted": check_id}


@router.post("/checks/{check_id}/unmute")
async def unmute_check(
    check_id: str,
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    await redis_client.srem(_MUTED_KEY, check_id)
    return {"unmuted": check_id}


def _age_seconds(dt: datetime | None) -> int | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - dt).total_seconds())


def _status_from_age(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age <= 3600:
        return "active"      # evento na última hora
    if age <= 86400:
        return "idle"        # sem eventos há < 24h
    return "stale"           # possivelmente parado


@router.get("/collection-points")
async def collection_points(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    """Pontos de coleta: fontes/conectores, checkpoints e atividade por DC."""
    # 1) Fontes configuradas (event_sources)
    sources = []
    for s in (await session.execute(select(EventSource).order_by(EventSource.name))).scalars().all():
        age = _age_seconds(s.last_event_at)
        sources.append({
            "name": s.name, "connector_type": s.connector_type, "endpoint": s.endpoint,
            "enabled": s.enabled, "status": s.status,
            "events_ingested": s.events_ingested, "errors_count": s.errors_count,
            "last_error": s.last_error,
            "last_event_at": s.last_event_at, "last_heartbeat_at": s.last_heartbeat_at,
            "last_event_age_s": age, "health": _status_from_age(age),
        })

    # 2) Checkpoints reais gravados pelo collector
    checkpoints = []
    for c in (await session.execute(
        select(CollectionCheckpoint).order_by(CollectionCheckpoint.source)
    )).scalars().all():
        checkpoints.append({
            "source": c.source, "channel": c.channel,
            "last_event_record_id": c.last_event_record_id,
            "last_event_time_utc": c.last_event_time_utc,
            "updated_at": c.updated_at,
            "lag_seconds": _age_seconds(c.last_event_time_utc),
        })

    # 3) Atividade real por Domain Controller (fonte da verdade: eventos)
    dc_rows = (await session.execute(text(
        """
        SELECT domain_controller AS dc,
               count(*) FILTER (WHERE event_time_utc > (now() AT TIME ZONE 'UTC') - interval '24 hours') AS c24,
               count(*) AS c7,
               max(event_time_utc) AS last_evt,
               count(DISTINCT event_type) AS types
        FROM normalized_events
        WHERE event_time_utc > (now() AT TIME ZONE 'UTC') - interval '7 days'
        GROUP BY domain_controller
        ORDER BY c7 DESC
        LIMIT 60
        """
    ))).all()
    dcs = []
    for r in dc_rows:
        age = _age_seconds(r[3])
        dcs.append({
            "dc": r[0], "events_24h": int(r[1]), "events_7d": int(r[2]),
            "last_event": r[3], "event_types": int(r[4]),
            "last_event_age_s": age, "status": _status_from_age(age),
        })

    active = sum(1 for d in dcs if d["status"] == "active")
    events_24h = sum(d["events_24h"] for d in dcs)
    return {
        "summary": {
            "sources": len(sources),
            "dcs_total": len(dcs),
            "dcs_active": active,
            "dcs_stale": sum(1 for d in dcs if d["status"] == "stale"),
            "events_24h": events_24h,
            "total_errors": sum(s["errors_count"] for s in sources),
        },
        "sources": sources,
        "checkpoints": checkpoints,
        "domain_controllers": dcs,
    }
