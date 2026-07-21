"""Health, readiness e métricas."""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.core.redis_client import ping as redis_ping
from app.database import engine

router = APIRouter()
settings = get_settings()


@router.get("/health", tags=["health"], summary="Liveness")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@router.get("/readiness", tags=["health"], summary="Readiness")
async def readiness(response: Response) -> dict:
    checks = {"database": False, "redis": False}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass
    checks["redis"] = await redis_ping()
    ready = all(checks.values())
    if not ready:
        response.status_code = 503
    return {"ready": ready, "checks": checks}


@router.get("/metrics", tags=["health"], summary="Métricas Prometheus")
async def metrics() -> Response:
    if not settings.prometheus_enabled:
        return Response(status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
