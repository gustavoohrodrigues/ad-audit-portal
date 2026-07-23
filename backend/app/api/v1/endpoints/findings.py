"""Security Operations — Central de Findings (vulnerabilidades, misconfig,
segredos, hardening) normalizados de múltiplos scanners.

Segurança:
- Leitura protegida por RBAC (critical:read); ingestão/supressão por
  investigation:manage. Toda ação de escrita é auditada.
- Ingestão valida e limita o payload (tamanho, nº de findings, tipos) e NUNCA
  executa comando — só faz parsing seguro. Segredos são mascarados nos adapters.
- Paginação limitada (anti-abuso); busca com ILIKE escapado (sem SQL cru).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.findings import FindingIngestion, SecurityFinding
from app.services import finding_service
from app.services.audit import record_audit
from app.services.finding_adapters import run_adapter
from app.services.finding_core import CATEGORIES, SEVERITIES

router = APIRouter(prefix="/security/findings", tags=["security-findings"])
settings = get_settings()

READ = require_capability("critical:read")
WRITE = require_capability("investigation:manage")


class IngestPayload(BaseModel):
    format: Literal["trivy", "normalized"]
    source_tool: Optional[str] = Field(default=None, max_length=64)
    environment: str = Field(default="unknown", max_length=64)
    asset_name: Optional[str] = Field(default=None, max_length=256)
    content: Any

    @field_validator("environment")
    @classmethod
    def _env(cls, v: str) -> str:
        return "".join(ch for ch in v if ch.isalnum() or ch in "-_.")[:64] or "unknown"


class SuppressPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    days: int = Field(default=30, ge=1, le=365)


class StatePayload(BaseModel):
    remediation_state: Literal["none", "in_progress", "fixed", "wont_fix"]
    assignee: Optional[str] = Field(default=None, max_length=128)


def _esc_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/overview")
async def findings_overview(
    session: AsyncSession = Depends(get_session), user: CurrentUser = Depends(READ),
) -> dict:
    return await finding_service.overview(session)


@router.get("/ingestions")
async def list_ingestions(
    session: AsyncSession = Depends(get_session), user: CurrentUser = Depends(READ),
) -> dict:
    rows = (await session.execute(
        select(FindingIngestion).order_by(FindingIngestion.created_at.desc()).limit(50)
    )).scalars().all()
    return {"items": [{
        "ingestion_id": r.ingestion_id, "source_tool": r.source_tool, "source_format": r.source_format,
        "asset_name": r.asset_name, "environment": r.environment, "total": r.total,
        "created": r.created, "updated": r.updated, "status": r.status,
        "created_by": r.created_by, "created_at": r.created_at,
    } for r in rows]}


@router.get("")
async def list_findings(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(READ),
    q: Optional[str] = Query(default=None, max_length=120),
    severity: Optional[str] = None,
    category: Optional[str] = None,
    asset_type: Optional[str] = None,
    environment: Optional[str] = None,
    status: str = "open",
    source_tool: Optional[str] = None,
    min_score: int = Query(default=0, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1),
) -> dict:
    page_size = min(page_size, settings.findings_max_page_size)
    stmt = select(SecurityFinding)
    if status in ("open", "suppressed", "resolved"):
        stmt = stmt.where(SecurityFinding.status == status)
    if severity in SEVERITIES:
        stmt = stmt.where(SecurityFinding.severity == severity)
    if category in CATEGORIES:
        stmt = stmt.where(SecurityFinding.category == category)
    if asset_type:
        stmt = stmt.where(SecurityFinding.asset_type == asset_type[:32])
    if environment:
        stmt = stmt.where(SecurityFinding.environment == environment[:64])
    if source_tool:
        stmt = stmt.where(SecurityFinding.source_tool == source_tool[:64])
    if min_score:
        stmt = stmt.where(SecurityFinding.risk_score >= min_score)
    if q:
        like = f"%{_esc_like(q)}%"
        stmt = stmt.where(or_(
            SecurityFinding.title.ilike(like), SecurityFinding.asset_name.ilike(like),
            SecurityFinding.cve.ilike(like), SecurityFinding.package_name.ilike(like),
        ))

    total = (await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    rows = (await session.execute(
        stmt.order_by(SecurityFinding.risk_score.desc(), SecurityFinding.last_seen.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [finding_service._row(f) for f in rows]}


@router.get("/{finding_id}")
async def get_finding(
    finding_id: int, session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(READ),
) -> dict:
    f = await session.get(SecurityFinding, finding_id)
    if not f:
        raise HTTPException(404, "Finding não encontrado")
    return finding_service.detail(f)


@router.post("/ingest")
async def ingest(
    payload: IngestPayload, request: Request,
    session: AsyncSession = Depends(get_session), user: CurrentUser = Depends(WRITE),
) -> dict:
    # guarda de tamanho (anti-DoS) antes de processar
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > settings.findings_ingest_max_bytes:
        raise HTTPException(413, "Payload de ingestão excede o limite permitido.")
    meta = {"environment": payload.environment, "asset_name": payload.asset_name,
            "source_tool": payload.source_tool or payload.format}
    try:
        canonical = run_adapter(payload.format, payload.content, meta)
    except ValueError as exc:
        raise HTTPException(400, f"Ingestão inválida: {exc}")
    except Exception:  # noqa: BLE001 — nunca vaza stacktrace de parsing
        raise HTTPException(400, "Falha ao processar o arquivo de scan (formato inesperado).")

    result = await finding_service.ingest_findings(
        session, canonical, source_tool=meta["source_tool"], source_format=payload.format,
        environment=payload.environment, asset_name=payload.asset_name, created_by=user.username,
    )
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="findings_ingest",
        resource=f"findings:{payload.format}", ip_address=request.client.host if request.client else None,
        detail=result,
    )
    return {"ok": True, **result}


@router.post("/{finding_id}/suppress")
async def suppress(
    finding_id: int, payload: SuppressPayload, request: Request,
    session: AsyncSession = Depends(get_session), user: CurrentUser = Depends(WRITE),
) -> dict:
    from datetime import datetime, timedelta, timezone
    f = await session.get(SecurityFinding, finding_id)
    if not f:
        raise HTTPException(404, "Finding não encontrado")
    f.status = "suppressed"
    f.suppressed_until = datetime.now(timezone.utc) + timedelta(days=payload.days)
    f.suppression_reason = payload.reason
    f.suppressed_by = user.username
    f.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="finding_suppress",
        resource=f"finding:{finding_id}", ip_address=request.client.host if request.client else None,
        detail={"reason": payload.reason, "days": payload.days, "until": str(f.suppressed_until)},
    )
    return {"ok": True, "status": f.status, "suppressed_until": f.suppressed_until}


@router.post("/{finding_id}/state")
async def set_state(
    finding_id: int, payload: StatePayload, request: Request,
    session: AsyncSession = Depends(get_session), user: CurrentUser = Depends(WRITE),
) -> dict:
    from datetime import datetime, timezone
    f = await session.get(SecurityFinding, finding_id)
    if not f:
        raise HTTPException(404, "Finding não encontrado")
    f.remediation_state = payload.remediation_state
    if payload.assignee is not None:
        f.assignee = payload.assignee
    if payload.remediation_state == "fixed":
        f.status = "resolved"
    elif f.status == "resolved" and payload.remediation_state != "fixed":
        f.status = "open"
    f.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="finding_state",
        resource=f"finding:{finding_id}", ip_address=request.client.host if request.client else None,
        detail={"remediation_state": payload.remediation_state, "assignee": payload.assignee},
    )
    return {"ok": True, "status": f.status, "remediation_state": f.remediation_state}
