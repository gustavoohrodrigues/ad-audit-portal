"""Endpoints de alertas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.enums import AlertStatus
from app.models.ops import Alert
from app.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    status: AlertStatus | None = None,
    severity: str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> list[AlertOut]:
    stmt = select(Alert)
    if status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    stmt = stmt.order_by(Alert.created_at.desc()).limit(min(limit, 500))
    rows = (await session.execute(stmt)).scalars().all()
    return [AlertOut.model_validate(a) for a in rows]


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("investigation:manage")),
) -> AlertOut:
    alert = await session.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_by = user.username
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)
