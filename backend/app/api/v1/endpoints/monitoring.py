"""Painel de Saúde & Alertas (estilo Ceph) e feed de notificações.

- GET  /monitoring/health         -> status geral + health checks
- GET  /monitoring/notifications  -> resumo para o sino (contagem + itens)
- POST /monitoring/checks/{id}/mute e /unmute (admin) -> silenciar check
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability, require_role
from app.core.redis_client import redis_client
from app.database import get_session
from app.models.enums import AlertStatus, Role
from app.models.ops import Alert
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
