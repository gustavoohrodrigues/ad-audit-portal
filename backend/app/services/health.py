"""Motor de health checks estilo Ceph.

Avalia um conjunto de verificações sobre o estado atual (contas, máquinas,
coletor, DCs) e retorna um status geral (HEALTH_OK / HEALTH_WARN / HEALTH_ERR)
com a lista de checks ativos — cada um com id, severidade, resumo e detalhe.

Projetado para ser consumido pela interface (sino de notificações e painel de
Saúde) e, no futuro, empurrado para canais de chat via webhook.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.directory import ADComputer, ADUser, DomainController
from app.models.event import NormalizedEvent
from app.models.ops import EventSource

settings = get_settings()

_LEGACY_OS = ["%windows 7%", "%windows 8%", "%windows xp%", "%vista%",
              "%server 2003%", "%server 2008%"]

# severidades: "error" > "warning" > "ok"
SEV_ORDER = {"error": 3, "warning": 2, "ok": 1}


async def _count(session: AsyncSession, model, cond) -> int:
    return (
        await session.execute(select(func.count()).select_from(model).where(cond))
    ).scalar_one()


async def evaluate(session: AsyncSession, muted: set[str] | None = None) -> dict:
    muted = muted or set()
    now = datetime.now(timezone.utc)
    checks: list[dict] = []

    def add(cid, severity, summary, detail, count=0, link=None):
        checks.append({
            "id": cid,
            "severity": severity,
            "summary": summary,
            "detail": detail,
            "count": count,
            "link": link,
            "muted": cid in muted,
        })

    total_users = await _count(session, ADUser, ADUser.id.is_not(None)) or 1

    # --- Contas ---
    pnr = await _count(session, ADUser, ADUser.password_not_required.is_(True))
    if pnr:
        add("AD_PASSWORD_NOT_REQUIRED", "error",
            f"{pnr} conta(s) com 'Password Not Required'",
            "Contas que permitem senha em branco. Remova o flag PASSWD_NOTREQD.",
            pnr, "/posture")

    sidhist = await _count(
        session, ADUser,
        func.jsonb_array_length(func.cast(ADUser.sid_history, JSONB)) > 0)
    if sidhist:
        add("AD_SIDHISTORY", "error",
            f"{sidhist} conta(s) com SIDHistory",
            "SIDHistory pode ser usado para escalonamento de privilégio.",
            sidhist, "/posture")

    deleg = await _count(
        session, ADUser,
        func.jsonb_array_length(func.cast(ADUser.allowed_to_delegate_to, JSONB)) > 0)
    if deleg:
        add("AD_DELEGATION", "warning",
            f"{deleg} conta(s) com delegação Kerberos",
            "Delegação irrestrita/constrained pode permitir personificação.",
            deleg, "/posture")

    spn = await _count(
        session, ADUser,
        and_(func.jsonb_array_length(func.cast(ADUser.service_principal_name, JSONB)) > 0,
             ADUser.is_disabled.is_(False)))
    if spn:
        add("AD_KERBEROASTABLE", "warning",
            f"{spn} conta(s) de usuário com SPN (kerberoastable)",
            "Contas de usuário com SPN são alvo de Kerberoasting. Use senhas longas/gMSA.",
            spn, "/posture")

    never = await _count(session, ADUser, ADUser.password_never_expires.is_(True))
    if never > 50:
        add("AD_PWD_NEVER_EXPIRES", "warning",
            f"{never} conta(s) com senha que nunca expira",
            "Grande volume de contas sem expiração de senha aumenta o risco.",
            never, "/posture")

    inactive = await _count(
        session, ADUser,
        and_(ADUser.is_inactive.is_(True), ADUser.is_disabled.is_(False)))
    if inactive:
        sev = "warning" if inactive < 200 else "error"
        add("AD_STALE_ACCOUNTS", sev,
            f"{inactive} conta(s) inativa(s) ainda habilitada(s)",
            f"Sem logon há mais de {settings.inactive_account_days} dias. Considere desabilitar.",
            inactive, "/posture")

    priv = await _count(session, ADUser, ADUser.is_privileged.is_(True))
    if priv / total_users > 0.03:
        add("AD_PRIVILEGE_SPRAWL", "warning",
            f"{priv} contas privilegiadas ({priv/total_users*100:.1f}% do total)",
            "Proporção elevada de contas privilegiadas. Aplique menor privilégio.",
            priv, "/posture")

    # --- Máquinas ---
    legacy = await _count(
        session, ADComputer,
        or_(*[ADComputer.operating_system.ilike(p) for p in _LEGACY_OS]))
    if legacy:
        sev = "error" if legacy > 100 else "warning"
        add("AD_LEGACY_OS", sev,
            f"{legacy} máquina(s) com SO legado/sem suporte",
            "Sistemas fora de suporte não recebem correções de segurança.",
            legacy, "/computers")

    # --- Coleta / observabilidade ---
    d1 = now - timedelta(hours=24)
    ingested = await _count(session, NormalizedEvent, NormalizedEvent.ingested_at >= d1)
    if ingested == 0:
        add("COLLECTOR_NO_EVENTS", "warning",
            "Nenhum evento ingerido nas últimas 24h",
            "O coletor pode não estar recebendo eventos (WEF/SIEM). Verifique a fonte.",
            0, "/admin")

    down_sources = (
        await session.execute(
            select(EventSource.name).where(EventSource.status == "down"))
    ).scalars().all()
    if down_sources:
        add("SOURCE_DOWN", "error",
            f"{len(down_sources)} fonte(s) de eventos indisponível(is)",
            "Fontes: " + ", ".join(down_sources),
            len(down_sources), "/admin")

    # --- Domain Controllers ---
    dc_down = (
        await session.execute(
            select(DomainController.hostname).where(DomainController.status == "down"))
    ).scalars().all()
    if dc_down:
        add("DC_DOWN", "error",
            f"{len(dc_down)} DC(s) sem eventos recentes",
            "DCs: " + ", ".join(dc_down),
            len(dc_down), "/")

    # status geral (ignora checks silenciados)
    active = [c for c in checks if not c["muted"]]
    if any(c["severity"] == "error" for c in active):
        status = "HEALTH_ERR"
    elif any(c["severity"] == "warning" for c in active):
        status = "HEALTH_WARN"
    else:
        status = "HEALTH_OK"

    checks.sort(key=lambda c: (SEV_ORDER.get(c["severity"], 0), c["count"]), reverse=True)
    summary = {
        "error": sum(1 for c in active if c["severity"] == "error"),
        "warning": sum(1 for c in active if c["severity"] == "warning"),
        "muted": sum(1 for c in checks if c["muted"]),
    }
    return {"status": status, "summary": summary, "checks": checks, "evaluated_at": now}
