"""Central de Mensagens: filtra um público (ex.: senha prestes a expirar) e
envia UMA notificação (e-mail individual ou Google Chat) — ação ativa, fora do
AD, com RBAC + confirmação + auditoria.

E-mail: o domínio é sempre o configurado (NOTIFICATION_EMAIL_DOMAIN).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.analytics import ChatWebhook, NotificationDelivery
from app.models.directory import ADUser
from app.schemas import BroadcastRequest
from app.services import messaging
from app.services.audit import record_audit

router = APIRouter(prefix="/messaging", tags=["messaging"])
settings = get_settings()


def _now() -> datetime:
    # naive UTC (colunas datetime do modelo são sem timezone)
    return datetime.now(timezone.utc).replace(tzinfo=None)


# filtros de público disponíveis
FILTERS = {
    "password_expiring": "Senha prestes a expirar (≤ 14 dias)",
    "inactive": "Contas inativas ainda habilitadas",
    "never_expires": "Senha nunca expira",
    "password_not_required": "Password Not Required",
    "privileged": "Contas privilegiadas",
    "disabled": "Contas desabilitadas",
}


def _condition(filter_key: str):
    u = ADUser
    if filter_key == "password_expiring":
        return and_(
            u.password_expires_at.is_not(None),
            u.password_expires_at >= _now(),
            u.password_expires_at <= _now() + timedelta(days=14),
            u.is_disabled.is_(False),
        )
    if filter_key == "inactive":
        return and_(u.is_inactive.is_(True), u.is_disabled.is_(False))
    if filter_key == "never_expires":
        return u.password_never_expires.is_(True)
    if filter_key == "password_not_required":
        return u.password_not_required.is_(True)
    if filter_key == "privileged":
        return u.is_privileged.is_(True)
    if filter_key == "disabled":
        return u.is_disabled.is_(True)
    return None


def _resolve_email(u: ADUser) -> str:
    """Local part do usuário + domínio forçado (NOTIFICATION_EMAIL_DOMAIN)."""
    if u.mail and "@" in u.mail:
        local = u.mail.split("@")[0]
    elif u.user_principal_name and "@" in u.user_principal_name:
        local = u.user_principal_name.split("@")[0]
    else:
        local = u.sam_account_name
    return f"{local}@{settings.notification_email_domain}"


@router.get("/filters")
async def list_filters(
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    return {"filters": [{"key": k, "label": v} for k, v in FILTERS.items()],
            "email_domain": settings.notification_email_domain}


@router.get("/audience")
async def audience(
    filter: str = Query(...),
    limit: int = Query(1000, ge=1, le=5000),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    cond = _condition(filter)
    if cond is None:
        raise HTTPException(status_code=404, detail="Filtro desconhecido")
    rows = (
        await session.execute(select(ADUser).where(cond).order_by(ADUser.sam_account_name).limit(limit))
    ).scalars().all()
    return {
        "filter": filter,
        "label": FILTERS.get(filter, filter),
        "email_domain": settings.notification_email_domain,
        "count": len(rows),
        "items": [
            {
                "sam_account_name": u.sam_account_name,
                "display_name": u.display_name,
                "email": _resolve_email(u),
                "password_expires_at": u.password_expires_at,
            }
            for u in rows
        ],
    }


@router.post("/broadcast")
async def broadcast(
    payload: BroadcastRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("investigation:manage")),
) -> dict:
    """Envia a mensagem ao público filtrado. Requer confirmação explícita."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirmação explícita obrigatória (confirm=true)")

    cond = _condition(payload.audience_filter)
    if cond is None:
        raise HTTPException(status_code=404, detail="Filtro desconhecido")

    rows = (
        await session.execute(
            select(ADUser).where(cond).limit(settings.broadcast_max_recipients)
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=400, detail="Público vazio para o filtro selecionado")

    ip = request.client.host if request.client else None
    sent = failed = 0

    if payload.channel == "google_chat":
        wh = await session.get(ChatWebhook, payload.chat_webhook_id) if payload.chat_webhook_id else None
        if not wh or not wh.enabled:
            raise HTTPException(status_code=400, detail="Webhook do Google Chat inválido/desabilitado")
        summary = (
            f"{payload.message}\n\n({len(rows)} conta(s) no filtro "
            f"'{FILTERS.get(payload.audience_filter)}')"
        )
        result = messaging.send_to_chat_webhook(wh.url, payload.subject or "AD Audit Portal", summary)
        sent = 1 if result.ok else 0
        failed = 0 if result.ok else 1
        session.add(NotificationDelivery(
            correlation_id=result.correlation_id, channel="google_chat",
            target=wh.name, subject=payload.subject, status="sent" if result.ok else "failed",
            error=None if result.ok else result.message, requested_by=user.username,
            requester_role=user.role, justification=payload.justification,
            context={"filter": payload.audience_filter, "recipients": len(rows)},
        ))
    else:  # email — envio individual para cada conta (domínio forçado)
        for u in rows:
            email = _resolve_email(u)
            result = messaging.deliver("email", payload.subject or "AD Audit Portal", payload.message, target=email)
            if result.ok:
                sent += 1
            else:
                failed += 1
            session.add(NotificationDelivery(
                correlation_id=result.correlation_id, channel="email", target=email,
                subject=payload.subject, status="sent" if result.ok else "failed",
                error=None if result.ok else result.message, requested_by=user.username,
                requester_role=user.role, justification=payload.justification,
                context={"filter": payload.audience_filter, "about_user": u.sam_account_name},
            ))

    await session.commit()
    await record_audit(
        session, actor=user.username, actor_role=user.role, action="broadcast",
        resource=f"filter:{payload.audience_filter}:{payload.channel}", ip_address=ip,
        success=failed == 0,
        detail={
            "channel": payload.channel, "filter": payload.audience_filter,
            "recipients": len(rows), "sent": sent, "failed": failed,
            "justification": payload.justification,
        },
    )
    return {"channel": payload.channel, "recipients": len(rows), "sent": sent, "failed": failed}
