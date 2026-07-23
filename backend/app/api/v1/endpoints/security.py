"""Scan de segurança (nmap) — ação ativa FORA do AD.

RBAC (administrator) + confirmação + auditoria + allowlist de alvos. O scan roda
em background (asyncio) e o resultado é consultado por polling.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, require_capability, require_role
from app.database import get_session
from app.models.directory import DomainController
from app.models.enums import Role
from app.models.security import SecurityScan
from app.services import scanner
from app.services.audit import record_audit

router = APIRouter(prefix="/security", tags=["security"])
settings = get_settings()

# mantém referência forte às tasks em background (evita coleta prematura)
_bg_tasks: set = set()


class ScanRequest(BaseModel):
    target: str
    profile: str = "quick"
    confirm: bool = False


class TlsCheckRequest(BaseModel):
    host: str
    port: int = 636


@router.get("/scan-config")
async def scan_config(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    dcs = (await session.execute(select(DomainController))).scalars().all()
    suggested = [
        {"host": d.hostname, "ip": d.ip_address}
        for d in dcs if d.hostname or d.ip_address
    ]
    allowed = [t.strip() for t in settings.scan_allowed_targets.split(",") if t.strip()]
    return {
        "enabled": settings.scan_enabled,
        "profiles": scanner.profiles_public(),
        "allowed_targets": allowed,
        "include_known_dcs": settings.scan_include_known_dcs,
        "suggested_targets": suggested,
        "timeout_seconds": settings.scan_nmap_timeout_seconds,
    }


@router.get("/scans")
async def list_scans(
    limit: int = 40,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    rows = (await session.execute(
        select(SecurityScan).order_by(SecurityScan.created_at.desc()).limit(min(limit, 100))
    )).scalars().all()
    return {"items": [
        {
            "id": s.id, "target": s.target, "profile": s.profile, "status": s.status,
            "requested_by": s.requested_by, "hosts_up": s.hosts_up,
            "open_ports": s.open_ports, "risk_count": s.risk_count,
            "created_at": s.created_at, "finished_at": s.finished_at, "error": s.error,
        } for s in rows
    ]}


@router.get("/scans/{scan_id}")
async def get_scan(
    scan_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    s = await session.get(SecurityScan, scan_id)
    if not s:
        raise HTTPException(404, "Scan não encontrado")
    return {
        "id": s.id, "target": s.target, "profile": s.profile, "status": s.status,
        "requested_by": s.requested_by, "hosts_up": s.hosts_up, "open_ports": s.open_ports,
        "risk_count": s.risk_count, "summary": s.summary, "result": s.result,
        "error": s.error, "created_at": s.created_at, "started_at": s.started_at,
        "finished_at": s.finished_at,
    }


@router.delete("/scans/{scan_id}")
async def delete_scan(
    scan_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    s = await session.get(SecurityScan, scan_id)
    if not s:
        raise HTTPException(404, "Scan não encontrado")
    target = s.target
    await session.delete(s)
    await session.commit()
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="security_scan_delete",
        resource=f"scan:{scan_id}", ip_address=request.client.host if request.client else None,
        detail={"scan_id": scan_id, "target": target},
    )
    return {"ok": True, "deleted": scan_id}


@router.post("/scans")
async def create_scan(
    req: ScanRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    if not settings.scan_enabled:
        raise HTTPException(403, "Scan de segurança desabilitado (defina SCAN_ENABLED=true).")
    if not req.confirm:
        raise HTTPException(400, "Confirmação obrigatória para executar um scan.")
    if req.profile not in scanner.PROFILES:
        raise HTTPException(400, "Perfil de scan inválido.")

    ok, reason = await scanner.validate_target(req.target, session)
    if not ok:
        raise HTTPException(400, reason)

    # limite de concorrência
    running = (await session.execute(
        select(SecurityScan).where(SecurityScan.status.in_(["pending", "running"]))
    )).scalars().all()
    if len(running) >= settings.scan_max_concurrent:
        raise HTTPException(429, "Já existe um scan em andamento. Aguarde a conclusão.")

    scan = SecurityScan(
        target=req.target.strip(), profile=req.profile,
        status="pending", requested_by=user.username,
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    await record_audit(
        session, actor=user.username, actor_role=user.role, action="security_scan",
        resource=f"scan:{req.target}", ip_address=request.client.host if request.client else None,
        detail={"target": req.target, "profile": req.profile, "scan_id": scan.id},
    )

    # dispara o scan em background (não bloqueia a resposta)
    task = asyncio.create_task(scanner.run_scan_task(scan.id))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return {"ok": True, "scan_id": scan.id, "status": scan.status}


@router.post("/tls-check")
async def tls_check(
    req: TlsCheckRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    """Inspeciona o certificado/TLS de host:port (ex.: LDAPS 636). Alvo na allowlist."""
    if not settings.scan_enabled:
        raise HTTPException(403, "Módulo de scan desabilitado (SCAN_ENABLED=true).")
    if not (1 <= req.port <= 65535):
        raise HTTPException(400, "Porta inválida.")
    ok, reason = await scanner.validate_target(req.host, session)
    if not ok:
        raise HTTPException(400, reason)
    result = await scanner.check_tls(req.host.strip(), req.port)
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="tls_check",
        resource=f"tls:{req.host}:{req.port}",
        ip_address=request.client.host if request.client else None,
        detail={"host": req.host, "port": req.port, "days_left": result.get("days_left")},
    )
    return result
