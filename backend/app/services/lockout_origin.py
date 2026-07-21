"""Descoberta da origem de bloqueio de conta (Event 4740).

Baseado no comando PowerShell de referência:

    Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4740} |
      Where-Object {$_.Properties[0].Value -eq 'NOME_DO_USUARIO'} |
      Select-Object TimeCreated,
        @{Name="Origem do Bloqueio";Expression={$_.Properties[1].Value}}

No evento 4740: Properties[0] = usuário bloqueado, Properties[1] = computador de
origem (Caller Computer Name). O collector já normaliza isso em
``caller_computer``. Este serviço retorna:
  1) as origens já coletadas no banco (rápido, se houver WEF/coleta);
  2) o comando PowerShell pronto para o analista rodar no DC;
  3) opcionalmente, uma consulta AO VIVO via WinRM (se habilitado).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_DOTNET_DATE = re.compile(r"/Date\((\d+)\)/")


def _normalize_time(value: Any) -> str | None:
    """Converte /Date(ms)/ (.NET, do ConvertTo-Json) ou string ISO para ISO UTC."""
    if not value:
        return None
    s = str(value)
    m = _DOTNET_DATE.search(s)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).isoformat()
        except (ValueError, OverflowError):
            return None
    return s

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models.enums import EventType
from app.models.event import NormalizedEvent

logger = get_logger(__name__)
settings = get_settings()


def build_ps_command(username: str, live: bool = False) -> str:
    """Gera o comando PowerShell para o usuário informado (base no comando dado)."""
    safe = username.replace("'", "''")
    cmd = (
        "Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4740} | "
        "Where-Object {$_.Properties[0].Value -eq '" + safe + "'} | "
        "Select-Object TimeCreated, "
        "@{Name=\"Origem do Bloqueio\";Expression={$_.Properties[1].Value}}, "
        "@{Name=\"DC\";Expression={$_.MachineName}}"
    )
    if live:
        cmd += " | ConvertTo-Json -Compress"
    return cmd


async def from_database(session: AsyncSession, username: str) -> list[dict[str, Any]]:
    stmt = (
        select(NormalizedEvent)
        .where(
            NormalizedEvent.event_type == EventType.account_lockout,
            NormalizedEvent.target_username == username,
        )
        .order_by(NormalizedEvent.event_time_utc.desc())
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "time": e.event_time_utc,
            "origin": e.caller_computer,   # Properties[1] normalizado
            "domain_controller": e.domain_controller,
            "source_ip": e.source_ip,
        }
        for e in rows
    ]


def from_winrm_live(username: str) -> tuple[list[dict[str, Any]], str | None]:
    """Executa a consulta 4740 ao vivo nos DCs via WinRM. Retorna (itens, erro)."""
    if not (settings.winrm_enabled and settings.winrm_domain_controllers):
        return [], "WinRM desabilitado (defina WINRM_ENABLED=true e os DCs)."
    try:
        import json

        import winrm  # type: ignore
    except ImportError:
        return [], "pacote pywinrm indisponível no backend."

    dcs = [d.strip() for d in settings.winrm_domain_controllers.split(",") if d.strip()]
    proto = "https" if settings.winrm_use_ssl else "http"
    command = build_ps_command(username, live=True)
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for dc in dcs:
        try:
            sess = winrm.Session(
                f"{proto}://{dc}:{settings.winrm_port}/wsman",
                auth=(settings.winrm_username, settings.winrm_password),
                transport=settings.winrm_transport,
                server_cert_validation="validate" if settings.winrm_verify_tls else "ignore",
            )
            r = sess.run_ps(command)
            if r.status_code != 0:
                errors.append(f"{dc}: {r.std_err.decode('utf-8','replace')[:120]}")
                continue
            out = r.std_out.decode("utf-8", "replace").strip()
            if not out:
                continue
            parsed = json.loads(out)
            for it in (parsed if isinstance(parsed, list) else [parsed]):
                items.append({
                    "time": _normalize_time(it.get("TimeCreated")),
                    "origin": it.get("Origem do Bloqueio"),
                    "domain_controller": it.get("DC") or dc,
                    "source_ip": None,
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{dc}: {exc}")
    return items, ("; ".join(errors) or None)
