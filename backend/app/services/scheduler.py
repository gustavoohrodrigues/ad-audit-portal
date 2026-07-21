"""Agendador leve de sincronização do AD no backend.

Executa ``sync_users`` periodicamente (AD_SYNC_INTERVAL_MINUTES). Como o backend
pode rodar com múltiplos workers uvicorn, usa uma trava no Redis (SET NX EX)
para garantir que apenas um worker execute cada ciclo.

Somente leitura em relação ao AD.
"""
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.database import SessionLocal
from app.services.ad_sync import sync_all

logger = get_logger(__name__)
settings = get_settings()

_LOCK_KEY = "adsync:lock"


async def _run_once() -> None:
    interval = max(settings.ad_sync_interval_minutes, 1) * 60
    # trava para não duplicar entre workers; TTL < intervalo
    acquired = await redis_client.set(_LOCK_KEY, "1", nx=True, ex=interval - 5)
    if not acquired:
        return
    try:
        async with SessionLocal() as session:
            await sync_all(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha na sincronização agendada do AD: %s", exc)


async def posture_snapshot_loop() -> None:
    """Grava o snapshot diário de Security Score e postura (histórico/tendência)."""
    from app.services.posture import snapshot_daily

    await asyncio.sleep(30)  # deixa o primeiro sync popular os dados
    while True:
        acquired = await redis_client.set("posture:snapshot:lock", "1", nx=True, ex=3600)
        if acquired:
            try:
                async with SessionLocal() as session:
                    result = await snapshot_daily(session)
                logger.info("Snapshot de postura gravado: %s", result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Falha no snapshot de postura: %s", exc)
        await asyncio.sleep(6 * 3600)  # reavalia a cada 6h (idempotente por dia)


async def ad_sync_loop() -> None:
    if not (settings.ad_enabled and settings.ad_sync_enabled):
        logger.info("Sincronização do AD desabilitada (AD_SYNC_ENABLED=false).")
        return
    interval = max(settings.ad_sync_interval_minutes, 1) * 60
    logger.info("Agendador de sync do AD ativo (intervalo=%ds).", interval)
    # primeiro ciclo logo após o startup
    await asyncio.sleep(10)
    while True:
        await _run_once()
        await asyncio.sleep(interval)
