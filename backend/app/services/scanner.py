"""Módulo de scan de segurança (nmap) — varredura de infraestrutura autorizada.

SEGURANÇA (inegociável):
- Não toca no AD. É uma ação ativa FORA do AD, análoga a um pentest autorizado
  da própria infraestrutura.
- Só varre alvos na ALLOWLIST (CIDR/IP/hostname) ou DCs conhecidos do inventário.
- Execução via subprocess com lista de argumentos (SEM shell) -> sem injeção.
- TCP connect scan (-sT/-Pn), roda como usuário não-root, sem CAP_NET_RAW.
- Timeout rígido; um scan por vez (configurável).
- Todo scan é auditado na camada de API.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import SessionLocal
from app.models.directory import DomainController
from app.models.security import SecurityScan

logger = get_logger(__name__)
settings = get_settings()

# Alvo válido: hostname/IP/CIDR. Nunca começa com '-' (evita virar flag do nmap).
_TARGET_RE = re.compile(r"^(?!-)[A-Za-z0-9._:-]+(/\d{1,3})?$")

# Perfis curados e SEGUROS (nada de -sS/-O/scripts de exploração).
PROFILES: dict[str, dict[str, Any]] = {
    "quick": {
        "label": "Rápido (top 100 portas)",
        "note": "Descoberta rápida de portas comuns abertas.",
        "args": ["-sT", "-T4", "-F", "--open", "-Pn"],
    },
    "services": {
        "label": "Serviços & versões (top 200)",
        "note": "Detecção de serviço/versão nas portas mais comuns.",
        "args": ["-sT", "-T4", "-sV", "--top-ports", "200", "--open", "-Pn"],
    },
    "ad_exposure": {
        "label": "Exposição de AD (portas-alvo)",
        "note": "Verifica portas típicas de DC e sinaliza exposição de risco.",
        "args": ["-sT", "-T4", "-sV", "--open", "-Pn",
                 "-p", "21,23,53,88,135,139,389,445,464,636,3268,3269,3389,5985,5986,9389"],
    },
}

# Avaliação de risco por porta aberta (exposição de superfície).
_PORT_RISK: dict[int, dict[str, str]] = {
    23: {"sev": "critical", "msg": "Telnet exposto (texto puro) — desabilitar."},
    21: {"sev": "high", "msg": "FTP exposto (texto puro)."},
    3389: {"sev": "high", "msg": "RDP exposto — restringir a jump hosts / VPN."},
    445: {"sev": "medium", "msg": "SMB exposto — restringir a redes confiáveis."},
    139: {"sev": "medium", "msg": "NetBIOS exposto — legado, restringir."},
    5985: {"sev": "high", "msg": "WinRM HTTP (5985) sem TLS — preferir 5986."},
    135: {"sev": "low", "msg": "RPC endpoint mapper exposto."},
}


def profiles_public() -> list[dict[str, str]]:
    return [{"id": k, "label": v["label"], "note": v["note"]} for k, v in PROFILES.items()]


def _allowed_networks() -> list[ipaddress._BaseNetwork]:
    nets: list[Any] = []
    for entry in settings.scan_allowed_targets.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            pass
    return nets


def _allowed_hostnames() -> set[str]:
    out = set()
    for entry in settings.scan_allowed_targets.split(","):
        entry = entry.strip().lower()
        if entry and not _looks_like_ip_or_cidr(entry):
            out.add(entry)
    return out


def _looks_like_ip_or_cidr(s: str) -> bool:
    try:
        ipaddress.ip_network(s, strict=False)
        return True
    except ValueError:
        return False


async def validate_target(target: str, session: AsyncSession) -> tuple[bool, str]:
    """Retorna (ok, motivo). Alvo precisa estar na allowlist ou ser um DC conhecido."""
    target = (target or "").strip()
    if not _TARGET_RE.match(target):
        return False, "Alvo inválido (use hostname, IP ou CIDR)."

    # 1) IP/CIDR -> precisa ser subconjunto de uma rede permitida
    if _looks_like_ip_or_cidr(target):
        net = ipaddress.ip_network(target, strict=False)
        for allowed in _allowed_networks():
            if net.version == allowed.version and net.subnet_of(allowed):
                return True, "ok"
        # IP pode bater com o IP de um DC conhecido
        if settings.scan_include_known_dcs and net.num_addresses == 1:
            ip = str(net.network_address)
            dcs = (await session.execute(select(DomainController))).scalars().all()
            if any((d.ip_address or "") == ip for d in dcs):
                return True, "ok"
        return False, "IP/CIDR fora da allowlist de scan."

    # 2) hostname -> allowlist explícita ou DC conhecido
    host = target.lower()
    if host in _allowed_hostnames():
        return True, "ok"
    if settings.scan_include_known_dcs:
        dcs = (await session.execute(select(DomainController))).scalars().all()
        if any((d.hostname or "").lower() == host for d in dcs):
            return True, "ok"
    return False, "Hostname fora da allowlist e não é um DC conhecido."


def _evaluate_risks(ports: list[dict]) -> list[dict]:
    risks: list[dict] = []
    open_ports = {p["port"] for p in ports if p["state"] == "open"}
    for port in open_ports:
        r = _PORT_RISK.get(port)
        if r:
            risks.append({"severity": r["sev"], "port": port, "message": r["msg"]})
    # LDAP sem LDAPS
    if 389 in open_ports and 636 not in open_ports:
        risks.append({"severity": "medium", "port": 389,
                      "message": "LDAP (389) aberto sem LDAPS (636) — exigir canal seguro."})
    return risks


def _parse_nmap_xml(xml: str) -> tuple[list[dict], dict]:
    hosts: list[dict] = []
    root = ET.fromstring(xml)
    for host in root.findall("host"):
        st = host.find("status")
        if st is not None and st.get("state") != "up":
            continue
        addr = ""
        for a in host.findall("address"):
            if a.get("addrtype") in ("ipv4", "ipv6"):
                addr = a.get("addr", "")
                break
        hostname = ""
        hn = host.find("hostnames/hostname")
        if hn is not None:
            hostname = hn.get("name", "")
        ports: list[dict] = []
        for p in host.findall("ports/port"):
            state_el = p.find("state")
            state = state_el.get("state") if state_el is not None else "unknown"
            svc = p.find("service")
            ports.append({
                "port": int(p.get("portid", 0)),
                "proto": p.get("protocol", "tcp"),
                "state": state,
                "service": (svc.get("name") if svc is not None else "") or "",
                "product": (svc.get("product") if svc is not None else "") or "",
                "version": (svc.get("version") if svc is not None else "") or "",
            })
        ports.sort(key=lambda x: x["port"])
        risks = _evaluate_risks(ports)
        hosts.append({"ip": addr, "hostname": hostname, "ports": ports, "risks": risks})
    summary = {
        "hosts_up": len(hosts),
        "open_ports": sum(len([p for p in h["ports"] if p["state"] == "open"]) for h in hosts),
        "risk_count": sum(len(h["risks"]) for h in hosts),
    }
    return hosts, summary


async def run_scan_task(scan_id: int) -> None:
    """Executa o nmap para um scan já persistido (rodar via asyncio.create_task)."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        scan = await session.get(SecurityScan, scan_id)
        if not scan:
            return
        profile = PROFILES.get(scan.profile) or PROFILES["quick"]
        scan.status = "running"
        scan.started_at = now
        await session.commit()
        target = scan.target

    cmd = ["nmap", *profile["args"], "-oX", "-", target]
    status, result, summary, error = "done", {}, {}, None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=settings.scan_nmap_timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("Tempo limite do scan excedido")
        if proc.returncode != 0:
            raise RuntimeError((err or b"").decode("utf-8", "ignore")[:300] or "nmap falhou")
        hosts, summary = _parse_nmap_xml(out.decode("utf-8", "ignore"))
        result = {"hosts": hosts}
    except FileNotFoundError:
        status, error = "error", "nmap não está instalado no container."
    except Exception as exc:  # noqa: BLE001
        status, error = "error", str(exc)[:400]
        logger.warning("Scan %s falhou: %s", scan_id, error)

    async with SessionLocal() as session:
        scan = await session.get(SecurityScan, scan_id)
        if not scan:
            return
        scan.status = status
        scan.error = error
        scan.result = result
        scan.summary = summary
        scan.hosts_up = summary.get("hosts_up", 0)
        scan.open_ports = summary.get("open_ports", 0)
        scan.risk_count = summary.get("risk_count", 0)
        scan.finished_at = datetime.now(timezone.utc)
        await session.commit()
