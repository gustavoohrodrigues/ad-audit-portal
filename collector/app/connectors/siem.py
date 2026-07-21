"""Conectores SIEM alternativos: Elastic, Wazuh, Graylog, Splunk, API genérica.

Cada um consulta os eventos do Windows Security já centralizados no SIEM. As
implementações usam httpx e retornam os documentos brutos para o normalizer.
Marcados como opcionais — habilite via EVENT_COLLECTOR_MODE.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import config
from app.connectors.base import BaseConnector

_WIN_EVENT_IDS = [
    4624, 4625, 4720, 4722, 4723, 4724, 4725, 4726, 4728, 4732, 4756,
    4729, 4733, 4757, 4738, 4740, 4767, 4771, 4776, 4781, 5136, 5137, 5141,
]


class ElasticConnector(BaseConnector):
    name = "Elastic"

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        query = {
            "size": config.batch_size,
            "sort": [{"@timestamp": "asc"}],
            "query": {"terms": {"winlog.event_id": [str(i) for i in _WIN_EVENT_IDS]}},
        }
        headers = {"Authorization": f"ApiKey {config.elastic_api_key}"}
        url = f"{config.elastic_url}/{config.elastic_index}/_search"
        async with httpx.AsyncClient(verify=True, timeout=30) as client:
            resp = await client.post(url, json=query, headers=headers)
            resp.raise_for_status()
            for hit in resp.json().get("hits", {}).get("hits", []):
                yield hit.get("_source", {})

    async def test(self) -> tuple[bool, str]:
        return bool(config.elastic_url), f"Elastic: {config.elastic_url or 'não configurado'}"


class GraylogConnector(BaseConnector):
    name = "Graylog"

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        params = {
            "query": " OR ".join(f"winlogbeat_winlog_event_id:{i}" for i in _WIN_EVENT_IDS),
            "range": config.poll_interval * 2,
            "limit": config.batch_size,
        }
        headers = {"Accept": "application/json"}
        auth = (config.graylog_api_token, "token")
        url = f"{config.graylog_api_url}/search/universal/relative"
        async with httpx.AsyncClient(verify=True, timeout=30) as client:
            resp = await client.get(url, params=params, headers=headers, auth=auth)
            resp.raise_for_status()
            for msg in resp.json().get("messages", []):
                yield msg.get("message", {})

    async def test(self) -> tuple[bool, str]:
        return bool(config.graylog_api_url), f"Graylog: {config.graylog_api_url or 'n/d'}"


class SplunkConnector(BaseConnector):
    name = "Splunk"

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        search = (
            "search index=* sourcetype=WinEventLog:Security "
            + " OR ".join(f"EventCode={i}" for i in _WIN_EVENT_IDS)
            + " | head " + str(config.batch_size) + " | to_json"
        )
        headers = {"Authorization": f"Bearer {config.splunk_api_token}"}
        url = f"{config.splunk_api_url}/services/search/jobs/export"
        async with httpx.AsyncClient(verify=True, timeout=60) as client:
            resp = await client.post(
                url, data={"search": search, "output_mode": "json"}, headers=headers
            )
            resp.raise_for_status()
            import json
            for line in resp.text.splitlines():
                try:
                    yield json.loads(line).get("result", {})
                except json.JSONDecodeError:
                    continue

    async def test(self) -> tuple[bool, str]:
        return bool(config.splunk_api_url), f"Splunk: {config.splunk_api_url or 'n/d'}"


class WazuhConnector(BaseConnector):
    name = "Wazuh"

    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        async with httpx.AsyncClient(verify=True, timeout=30) as client:
            auth_resp = await client.post(
                f"{config.wazuh_api_url}/security/user/authenticate",
                auth=(config.wazuh_api_user, config.wazuh_api_password),
            )
            auth_resp.raise_for_status()
            token = auth_resp.json().get("data", {}).get("token")
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(
                f"{config.wazuh_api_url}/events",
                params={"limit": config.batch_size},
                headers=headers,
            )
            resp.raise_for_status()
            for item in resp.json().get("data", {}).get("affected_items", []):
                yield item.get("data", {}).get("win", {})

    async def test(self) -> tuple[bool, str]:
        return bool(config.wazuh_api_url), f"Wazuh: {config.wazuh_api_url or 'n/d'}"


def get_connector(mode: str) -> BaseConnector:
    from app.connectors.wef import WEFConnector
    from app.connectors.winrm_conn import WinRMConnector

    return {
        "wef": WEFConnector,
        "winrm": WinRMConnector,
        "elastic": ElasticConnector,
        "graylog": GraylogConnector,
        "splunk": SplunkConnector,
        "wazuh": WazuhConnector,
    }.get(mode, WEFConnector)()
