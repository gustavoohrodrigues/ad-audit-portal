"""Portal de webhooks de chat (Google Chat). CRUD; URL nunca exibida na íntegra."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability, require_role
from app.database import get_session
from app.models.analytics import ChatWebhook
from app.models.enums import Role
from app.schemas import ChatWebhookCreate
from app.services import messaging
from app.services.audit import record_audit

router = APIRouter(prefix="/chat-webhooks", tags=["chat-webhooks"])


def _mask_url(url: str) -> str:
    """Exibe apenas o início e o fim da URL (nunca o token inteiro)."""
    if len(url) <= 40:
        return url[:20] + "…"
    return url[:34] + "…" + url[-8:]


@router.get("")
async def list_webhooks(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    rows = (await session.execute(select(ChatWebhook).order_by(ChatWebhook.created_at))).scalars().all()
    return {
        "items": [
            {
                "id": w.id, "name": w.name, "provider": w.provider,
                "url_masked": _mask_url(w.url), "enabled": w.enabled,
                "created_by": w.created_by, "created_at": w.created_at,
            }
            for w in rows
        ]
    }


@router.post("")
async def create_webhook(
    payload: ChatWebhookCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    if payload.provider == "google_chat" and not messaging.is_google_chat_url(payload.url):
        raise HTTPException(
            status_code=400,
            detail="A URL deve ser um webhook do Google Chat (https://chat.googleapis.com/...)",
        )
    wh = ChatWebhook(
        name=payload.name, provider=payload.provider, url=payload.url,
        created_by=user.username,
    )
    session.add(wh)
    await session.commit()
    await session.refresh(wh)
    await record_audit(
        session, actor=user.username, actor_role=user.role,
        action="chat_webhook_create", resource=f"chat_webhook:{wh.name}",
        ip_address=request.client.host if request.client else None,
        detail={"provider": wh.provider},  # URL NÃO é registrada
    )
    return {"id": wh.id, "name": wh.name}


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_role(Role.administrator)),
) -> dict:
    wh = await session.get(ChatWebhook, webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    await session.delete(wh)
    await session.commit()
    await record_audit(
        session, actor=user.username, actor_role=user.role,
        action="chat_webhook_delete", resource=f"chat_webhook:{wh.name}",
        ip_address=request.client.host if request.client else None,
    )
    return {"deleted": webhook_id}
