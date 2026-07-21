"""Conector WinRM alternativo — lê o log Security dos DCs via WS-Man.

Usa uma conta de LEITURA de Event Log (Event Log Readers). Requer o pacote
opcional `pywinrm`. Habilite com WINRM_ENABLED=true e EVENT_COLLECTOR_MODE=winrm.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.config import config
from app.connectors.base import BaseConnector

# Consulta os Event IDs de interesse desde o último RecordID conhecido.
_PS_TEMPLATE = (
    "$ids=@({ids}); "
    "Get-WinEvent -FilterHashtable @{{LogName='Security';Id=$ids}} "
    "-MaxEvents {max} | Where-Object {{ $_.RecordId -gt {last} }} "
    "| ForEach-Object {{ $_.ToXml() }}"
)

EVENT_IDS = [
    4624, 4625, 4720, 4722, 4723, 4724, 4725, 4726, 4728, 4732, 4756,
    4729, 4733, 4757, 4738, 4740, 4767, 4771, 4776, 4781, 5136, 5137, 5141,
]


class WinRMConnector(BaseConnector):
    name = "WinRM"

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        try:
            import winrm  # type: ignore
            import xmltodict  # type: ignore
        except ImportError:
            raise RuntimeError(
                "pywinrm/xmltodict não instalados — adicione ao requirements do collector"
            )
        last = (checkpoint or {}).get("last_record_id") or 0
        for dc in config.winrm_dcs:
            proto = "https" if config.winrm_use_ssl else "http"
            session = winrm.Session(
                f"{proto}://{dc}:{config.winrm_port}/wsman",
                auth=(config.winrm_username, config.winrm_password),
                transport=config.winrm_transport,
                server_cert_validation="validate" if config.winrm_verify_tls else "ignore",
            )
            ps = _PS_TEMPLATE.format(
                ids=",".join(str(i) for i in EVENT_IDS),
                max=config.batch_size,
                last=last,
            )
            result = session.run_ps(ps)
            if result.status_code != 0:
                continue
            for xml_block in result.std_out.decode("utf-8", "replace").split("</Event>"):
                xml_block = xml_block.strip()
                if not xml_block:
                    continue
                try:
                    parsed = xmltodict.parse(xml_block + "</Event>")
                    yield _flatten_event(parsed.get("Event", {}))
                except Exception:  # noqa: BLE001
                    continue

    async def test(self) -> tuple[bool, str]:
        if not config.winrm_dcs:
            return False, "WINRM_DOMAIN_CONTROLLERS vazio"
        return True, f"WinRM configurado para {len(config.winrm_dcs)} DC(s)"


def _flatten_event(event: dict) -> dict:
    """Converte o dict do xmltodict para o formato System/EventData esperado."""
    system = event.get("System", {})
    data = event.get("EventData", {}).get("Data", [])
    event_data: dict[str, Any] = {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "@Name" in item:
                event_data[item["@Name"]] = item.get("#text")
    return {
        "System": {
            "EventID": (system.get("EventID", {}) or {}).get("#text")
            if isinstance(system.get("EventID"), dict)
            else system.get("EventID"),
            "Computer": system.get("Computer"),
            "EventRecordID": system.get("EventRecordID"),
            "TimeCreated": (system.get("TimeCreated", {}) or {}).get("@SystemTime"),
        },
        "EventData": event_data,
    }
