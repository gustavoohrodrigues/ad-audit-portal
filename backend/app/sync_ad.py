"""Entrypoint de sincronização do AD (execução manual/agendada).

Uso:  python -m app.sync_ad
Somente leitura — apenas lê o AD e popula/atualiza ad_users.
"""
from __future__ import annotations

import asyncio

from app.core.logging import configure_logging, get_logger
from app.config import get_settings
from app.database import SessionLocal
from app.services.ad_sync import sync_all

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)
logger = get_logger(__name__)


async def main() -> None:
    async with SessionLocal() as session:
        result = await sync_all(session)
    logger.info("Sincronização finalizada: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
