"""Loop principal do collector: coleta -> normaliza -> dedup/insere -> checkpoint.

Processamento assíncrono com intervalo configurável. A deduplicação é garantida
pelo índice único no banco; o checkpoint por fonte evita reprocessamento amplo.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from app.config import config
from app.connectors.siem import get_connector
from app.db import (
    get_checkpoint,
    insert_events,
    update_checkpoint,
    update_source_stats,
)
from app.normalizer import normalize

logging.basicConfig(
    level=config.log_level,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
log = logging.getLogger("collector")

_stop = asyncio.Event()


def _handle_signal(*_: object) -> None:
    log.info("Sinal de parada recebido")
    _stop.set()


async def collect_once() -> None:
    connector = get_connector(config.mode)
    checkpoint = await get_checkpoint(connector.name)
    batch: list[dict] = []
    max_record_id = (checkpoint or {}).get("last_record_id") or 0
    latest_time: datetime | None = None
    errors = 0

    async for raw in connector.fetch(checkpoint):
        try:
            normalized = normalize(raw, collector_source=connector.name)
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao normalizar evento: %s", exc)
            errors += 1
            continue
        if not normalized:
            continue
        batch.append(normalized)
        rid = normalized.get("event_record_id") or 0
        max_record_id = max(max_record_id, rid)
        et = normalized["event_time_utc"]
        latest_time = et if latest_time is None or et > latest_time else latest_time

        if len(batch) >= config.batch_size:
            await _flush(connector.name, batch, max_record_id, latest_time, errors)
            batch, errors = [], 0

    if batch:
        await _flush(connector.name, batch, max_record_id, latest_time, errors)
    else:
        # heartbeat mesmo sem eventos
        await update_source_stats(connector.name, 0, errors, latest_time, "healthy")


async def _flush(
    source: str, batch: list[dict], max_rid: int, latest_time, errors: int
) -> None:
    inserted = await insert_events(batch)
    await update_checkpoint(source, "Security", max_rid, latest_time)
    await update_source_stats(source, inserted, errors, latest_time, "healthy")
    log.info(
        "Fonte=%s recebidos=%d inseridos=%d duplicados=%d erros=%d",
        source, len(batch), inserted, len(batch) - inserted, errors,
    )


async def run() -> None:
    config.validate()
    if not config.enabled:
        log.warning("Collector desabilitado (EVENT_COLLECTOR_ENABLED=false). Em espera.")
        await _stop.wait()
        return
    log.info("Collector iniciado no modo '%s' (intervalo=%ss)", config.mode, config.poll_interval)
    while not _stop.is_set():
        try:
            await collect_once()
        except Exception as exc:  # noqa: BLE001
            log.error("Erro no ciclo de coleta: %s", exc)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=config.poll_interval)
        except asyncio.TimeoutError:
            pass
    log.info("Collector encerrado")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass
    try:
        loop.run_until_complete(run())
    finally:
        loop.close()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        log.error("Falha de inicialização: %s", exc)
        sys.exit(1)
