"""Manutenção do banco (admin): status e limpeza sob demanda. Auditado."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability, require_role
from app.core.redis_client import redis_client
from app.database import get_session
from app.models.enums import Role
from app.services import maintenance
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/maintenance", tags=["maintenance"])


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    return await maintenance.maintenance_status(session)


@router.post("/cleanup")
async def cleanup(
    request: Request,
    vacuum: bool | None = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    """Executa a limpeza/retenção do banco agora. Protegido contra concorrência."""
    lock = await redis_client.set("maintenance:cleanup:lock", "1", nx=True, ex=1800)
    if not lock:
        return {"ok": False, "message": "Uma limpeza já está em andamento"}
    try:
        stats = await maintenance.run_cleanup(session, vacuum=vacuum)
        await record_audit(
            session, actor=user.username, actor_role=user.role, action="db_cleanup",
            resource="maintenance", ip_address=request.client.host if request.client else None,
            detail=stats,
        )
        return {"ok": True, "stats": stats}
    finally:
        await redis_client.delete("maintenance:cleanup:lock")
