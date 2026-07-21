"""Serviço de auditoria interna: registra login, logout, acesso a JSON bruto,
exportações e buscas. Nunca grava senha/token."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ops import InternalAuditLog

settings = get_settings()


async def record_audit(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    actor_role: str | None = None,
    resource: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    detail: dict[str, Any] | None = None,
) -> None:
    if not settings.audit_log_enabled:
        return
    # remove chaves sensíveis do detail por precaução
    safe_detail = {
        k: v
        for k, v in (detail or {}).items()
        if not any(s in k.lower() for s in ("pass", "senha", "token", "secret"))
    }
    entry = InternalAuditLog(
        actor=actor,
        actor_role=actor_role,
        action=action,
        resource=resource,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:400] or None,
        success=success,
        detail=safe_detail,
    )
    session.add(entry)
    await session.commit()
