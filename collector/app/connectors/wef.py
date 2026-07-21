"""Conector WEF (Windows Event Forwarding) — modo primário.

Arquitetura recomendada (ver docs/wef.md):
  DCs --(subscription Source Initiated)--> Windows Event Collector (ForwardedEvents)
  --> exportador (NXLog/WEC-to-JSON/tarefa PowerShell) --> arquivos NDJSON no spool.

Este conector consome os arquivos NDJSON do diretório de spool, um evento por
linha, e move os arquivos processados para .done. É robusto a reprocessamento
porque a deduplicação ocorre no banco (índice único).
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.config import config
from app.connectors.base import BaseConnector


class WEFConnector(BaseConnector):
    name = "WEF-ForwardedEvents"

    def __init__(self) -> None:
        self.spool = Path(config.wef_spool_dir)

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        if not self.spool.exists():
            self.spool.mkdir(parents=True, exist_ok=True)
            return
        files = sorted(self.spool.glob("*.ndjson")) + sorted(self.spool.glob("*.json"))
        for fpath in files:
            try:
                with fpath.open("r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
                # marca como processado
                fpath.rename(fpath.with_suffix(fpath.suffix + ".done"))
            except OSError:
                continue

    async def test(self) -> tuple[bool, str]:
        exists = self.spool.exists()
        writable = exists and os.access(self.spool, os.R_OK)
        if not exists:
            return False, f"Spool WEF inexistente: {self.spool}"
        return writable, f"Spool WEF acessível em {self.spool}"
