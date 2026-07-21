"""Ações ativas de notificação e histórico de entregas.

POST /users/{id}/notify vive aqui (montado no router de users por conveniência
de URL) — envia mensagem por um canal autorizado, com RBAC, confirmação
explícita, sanitização e auditoria completa. NUNCA altera o AD.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.analytics import NotificationDelivery
from app.schemas import NotifyRequest
from app.services import messaging
from app.services.audit import record_audit

router = APIRouter(tags=["notifications"])


@router.post("/users/{identifier}/notify")
async def notify_user(
    identifier: str,
    payload: NotifyRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("investigation:manage")),
) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirmação explícita é obrigatória (confirm=true)")

    ip = request.client.host if request.client else None
    result = messaging.deliver(
        channel=payload.channel,
        subject=payload.subject,
        body=payload.message,
        target=payload.target or identifier,
    )

    delivery = NotificationDelivery(
        correlation_id=result.correlation_id,
        channel=payload.channel,
        target=payload.target or identifier,
        subject=payload.subject,
        status="sent" if result.ok else "failed",
        error=None if result.ok else result.message,
        requested_by=user.username,
        requester_role=user.role,
        justification=payload.justification,
        ticket_reference=payload.ticket_reference,
        context={"about_user": identifier},
    )
    session.add(delivery)
    await session.commit()

    await record_audit(
        session,
        actor=user.username,
        actor_role=user.role,
        action="notify",
        resource=f"user:{identifier}:{payload.channel}",
        ip_address=ip,
        success=result.ok,
        detail={
            "channel": payload.channel,
            "target": payload.target or identifier,
            "justification": payload.justification,
            "ticket": payload.ticket_reference,
            "correlation_id": result.correlation_id,
            "result": result.message,
        },
    )
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.message)
    return {"ok": True, "correlation_id": result.correlation_id, "message": result.message}


@router.get("/notifications/history")
async def notifications_history(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    rows = (
        await session.execute(
            select(NotificationDelivery)
            .order_by(NotificationDelivery.created_at.desc())
            .limit(min(limit, 500))
        )
    ).scalars().all()
    return {
        "items": [
            {
                "time": d.created_at,
                "channel": d.channel,
                "target": d.target,
                "subject": d.subject,
                "status": d.status,
                "error": d.error,
                "requested_by": d.requested_by,
                "role": d.requester_role,
                "ticket": d.ticket_reference,
                "correlation_id": d.correlation_id,
            }
            for d in rows
        ]
    }
