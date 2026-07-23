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
from app.models.enums import AlertStatus, Severity
from app.models.ops import Alert
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
    "smb_audit": {
        "label": "Auditoria SMB (SMBv1 / assinatura)",
        "note": "Detecta SMBv1 e assinatura não obrigatória via scripts NSE seguros.",
        "args": ["-sT", "-T4", "-p", "139,445", "--open", "-Pn",
                 "--script", "smb-protocols,smb2-security-mode,smb-os-discovery,smb2-time"],
    },
    "discovery": {
        "label": "Descoberta de hosts (ping sweep)",
        "note": "Lista hosts vivos numa faixa (sem varrer portas). Ideal para um /24.",
        "args": ["-sn", "-PS22,80,135,139,389,445,3389,5985", "-T4"],
    },
    "full": {
        "label": "Completo (todas as portas TCP)",
        "note": "Varre as 65535 portas TCP. Lento — aumente o timeout para faixas.",
        "args": ["-sT", "-T4", "-p-", "--open", "-Pn"],
    },
    "standard": {
        "label": "Padrão (top 1000 portas)",
        "note": "Varredura das 1000 portas mais comuns.",
        "args": ["-sT", "-T4", "--open", "-Pn"],
    },
    "scripts_default": {
        "label": "Scripts padrão (-sC) + versões",
        "note": "Scripts NSE padrão (seguros) + detecção de versão nas top 200.",
        "args": ["-sT", "-T4", "-sV", "-sC", "--top-ports", "200", "--open", "-Pn"],
    },
    "vuln_smb": {
        "label": "Vuln SMB (MS17-010 / MS08-067)",
        "note": "Detecção de EternalBlue (MS17-010) e MS08-067 via NSE (não explora).",
        "args": ["-sT", "-T4", "-p", "139,445", "--open", "-Pn",
                 "--script", "smb-vuln-ms17-010,smb-vuln-ms08-067"],
    },
    "web_audit": {
        "label": "Auditoria Web (HTTP/HTTPS)",
        "note": "Título, headers, métodos e certificado de serviços web.",
        "args": ["-sT", "-T4", "-sV", "-p", "80,443,8080,8443,8000", "--open", "-Pn",
                 "--script", "http-title,http-headers,http-methods,ssl-cert"],
    },
    "rdp_audit": {
        "label": "Auditoria RDP (NLA/criptografia)",
        "note": "Verifica NLA/CredSSP e nível de criptografia do RDP (3389).",
        "args": ["-sT", "-T4", "-sV", "-p", "3389", "--open", "-Pn",
                 "--script", "rdp-ntlm-info,rdp-enum-encryption"],
    },
    "dns_audit": {
        "label": "Auditoria DNS (recursão)",
        "note": "Detecta recursão aberta e identifica o servidor DNS (53).",
        "args": ["-sT", "-T4", "-sV", "-p", "53", "--open", "-Pn",
                 "--script", "dns-recursion,dns-nsid"],
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


def _script_risks(scripts: list[dict]) -> list[dict]:
    """Avalia riscos a partir da saída de scripts NSE (auditoria SMB etc.)."""
    risks: list[dict] = []
    for s in scripts:
        out = (s.get("output") or "").lower()
        sid = s.get("id", "")
        if sid == "smb-protocols" and ("smbv1" in out or "smb1" in out or "2.02" in out and "1.0" in out):
            risks.append({"severity": "high", "port": 445,
                          "message": "SMBv1 habilitado — desabilitar (EternalBlue/ransomware)."})
        if sid == "smb-protocols" and "1.0" in out:
            risks.append({"severity": "high", "port": 445,
                          "message": "SMB 1.0 negociável — desabilitar SMBv1."})
        if sid == "smb2-security-mode" and "not required" in out:
            risks.append({"severity": "medium", "port": 445,
                          "message": "Assinatura SMB não obrigatória — habilitar signing (anti-relay)."})
        # Vulnerabilidades SMB (detecção NSE)
        if sid.startswith("smb-vuln") and "vulnerable" in out and "not vulnerable" not in out:
            cve = "MS17-010 (EternalBlue)" if "ms17-010" in sid else "MS08-067"
            risks.append({"severity": "critical", "port": 445,
                          "message": f"VULNERÁVEL a {cve} — corrigir imediatamente."})
        # DNS recursão aberta
        if sid == "dns-recursion" and "recursion" in out and "enabled" in out:
            risks.append({"severity": "medium", "port": 53,
                          "message": "Recursão DNS aberta — restringir a redes internas."})
        # RDP sem NLA / criptografia fraca
        if sid == "rdp-enum-encryption" and ("rdp encryption level: low" in out or "rdp encryption level: none" in out):
            risks.append({"severity": "high", "port": 3389,
                          "message": "Criptografia RDP fraca — exigir TLS/NLA."})
        if sid == "rdp-ntlm-info" and "nla" in out and "false" in out:
            risks.append({"severity": "high", "port": 3389,
                          "message": "RDP sem NLA — habilitar Network Level Authentication."})
        # Métodos HTTP perigosos
        if sid == "http-methods" and ("trace" in out or "put" in out or "delete" in out):
            risks.append({"severity": "low", "port": 80,
                          "message": "Métodos HTTP potencialmente perigosos (TRACE/PUT/DELETE)."})
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
        # scripts NSE (host-level e por porta)
        scripts: list[dict] = []
        for sc in host.findall("hostscript/script"):
            scripts.append({"id": sc.get("id", ""), "output": (sc.get("output") or "").strip()[:1500]})
        for p in host.findall("ports/port"):
            for sc in p.findall("script"):
                scripts.append({"id": sc.get("id", ""), "output": (sc.get("output") or "").strip()[:1500]})
        risks = _evaluate_risks(ports) + _script_risks(scripts)
        hosts.append({"ip": addr, "hostname": hostname, "ports": ports,
                      "scripts": scripts, "risks": risks})
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

        if status == "done" and settings.scan_alerts_enabled:
            await _create_scan_alerts(session, scan, result.get("hosts", []))
        if status == "done" and settings.scan_findings_enabled:
            await _create_scan_findings(scan, result.get("hosts", []))


async def _create_scan_findings(scan, hosts: list[dict]) -> None:
    """Converte os riscos do scan em findings normalizados (central Security Ops)."""
    from app.services.finding_core import coerce_finding
    from app.services.finding_service import ingest_findings

    canonical = []
    for h in hosts:
        who = h.get("hostname") or h.get("ip") or scan.target
        for r in h.get("risks", []):
            canonical.append(coerce_finding({
                "source_tool": "nmap", "source_type": "host", "category": "exposure",
                "asset_type": "host", "asset_name": who, "host_name": who,
                "severity": r.get("severity", "medium"), "title": r.get("message", "Exposição"),
                "evidence": {"port": r.get("port"), "scan_target": scan.target, "profile": scan.profile},
                "remediation": r.get("message"),
            }))
    if not canonical:
        return
    async with SessionLocal() as session:
        await ingest_findings(session, canonical, source_tool="nmap", source_format="scan",
                              environment="infra", asset_name=scan.target,
                              created_by=scan.requested_by)


_SEV_MAP = {"critical": Severity.critical, "high": Severity.high,
            "medium": Severity.medium, "low": Severity.low, "info": Severity.info}
_SEV_SCORE = {"critical": 95, "high": 80, "medium": 55, "low": 30, "info": 10}


async def _create_scan_alerts(session, scan, hosts: list[dict]) -> None:
    """Converte achados de risco do scan em alertas (dedup por chave estável)."""
    created = 0
    for h in hosts:
        who = h.get("hostname") or h.get("ip") or scan.target
        for r in h.get("risks", []):
            dk = f"scan:{h.get('ip') or who}:{r.get('port', '')}:{r['message'][:48]}"
            exists = (await session.execute(
                select(Alert).where(Alert.dedup_key == dk, Alert.status == AlertStatus.open)
            )).first()
            if exists:
                continue
            sev = r.get("severity", "medium")
            session.add(Alert(
                title=f"[Scan] {who}: {r['message'][:110]}",
                description=f"Alvo {scan.target} · porta {r.get('port', '-')} · perfil {scan.profile}",
                severity=_SEV_MAP.get(sev, Severity.medium),
                risk_score=_SEV_SCORE.get(sev, 50),
                status=AlertStatus.open, dedup_key=dk,
                context={"host": h.get("ip") or who, "port": r.get("port"),
                         "scan_id": scan.id, "target": scan.target, "source": "security_scan"},
            ))
            created += 1
    if created:
        await session.commit()
        logger.info("Scan %s gerou %d alerta(s)", scan.id, created)


# ---------------------------------------------------------------------------
# Inspeção de TLS / certificado (host:port) — ação ativa, sem nmap.
# ---------------------------------------------------------------------------
_WEAK_TLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}


def _tls_inspect(host: str, port: int, timeout: int) -> dict:
    import socket
    import ssl as _ssl
    from datetime import datetime, timezone

    ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE  # inspecionamos até certificados self-signed
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ss:
            der = ss.getpeercert(binary_form=True)
            proto = ss.version() or ""
            cipher = ss.cipher()

    from cryptography import x509
    cert = x509.load_der_x509_certificate(der)
    now = datetime.now(timezone.utc)
    try:
        not_after = cert.not_valid_after_utc
        not_before = cert.not_valid_before_utc
    except AttributeError:  # cryptography < 42
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
    days_left = (not_after - now).days
    sans: list[str] = []
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = ext.value.get_values_for_type(x509.DNSName)
    except Exception:  # noqa: BLE001
        pass

    risks: list[dict] = []
    if days_left < 0:
        risks.append({"severity": "critical", "message": f"Certificado EXPIRADO há {-days_left} dias."})
    elif days_left <= 15:
        risks.append({"severity": "high", "message": f"Certificado expira em {days_left} dias."})
    elif days_left <= 30:
        risks.append({"severity": "medium", "message": f"Certificado expira em {days_left} dias."})
    if proto in _WEAK_TLS:
        risks.append({"severity": "high", "message": f"Protocolo TLS fraco negociado: {proto}."})
    if now < not_before:
        risks.append({"severity": "medium", "message": "Certificado ainda não é válido (notBefore futuro)."})

    return {
        "host": host, "port": port, "tls_version": proto,
        "cipher": cipher[0] if cipher else None,
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "days_left": days_left,
        "sans": sans[:20],
        "self_signed": cert.subject == cert.issuer,
        "risks": risks,
    }


async def check_tls(host: str, port: int) -> dict:
    """Inspeciona o certificado/protocolo TLS de host:port (roda em thread)."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_tls_inspect, host, port, min(settings.scan_nmap_timeout_seconds, 20)),
            timeout=25,
        )
    except Exception as exc:  # noqa: BLE001
        return {"host": host, "port": port, "error": str(exc)[:300], "risks": []}
