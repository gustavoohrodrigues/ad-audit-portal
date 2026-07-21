"""Endpoints de detecção defensiva (Superfície de Ataque). Somente leitura."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.services import detections
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("/summary")
async def summary(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    return await detections.summary(session)


@router.get("/kerberoasting")
async def kerberoasting(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    return await detections.kerberoasting(session)


@router.get("/asrep-roasting")
async def asrep(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    return await detections.asrep_roasting(session)


@router.get("/stale-admins")
async def stale_admins(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("critical:read")),
) -> dict:
    return await detections.stale_admins(session)
