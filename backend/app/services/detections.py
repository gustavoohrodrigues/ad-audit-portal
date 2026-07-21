"""Detecções defensivas baseadas nos objetos sincronizados (somente leitura).

Não executa nem tenta explorar credenciais — apenas classifica exposição, com
evidências e recomendações. Referências MITRE ATT&CK incluídas por transparência.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.directory import ADUser

settings = get_settings()


def _now() -> datetime:
    # naive UTC: as colunas datetime do modelo são 'timestamp without time zone',
    # então retornam naive. Comparações Python e SQL usam o mesmo referencial.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _spn_len_gt0():
    return func.jsonb_array_length(func.cast(ADUser.service_principal_name, JSONB)) > 0


def _risk(u: ADUser, base: int) -> int:
    r = base
    if u.is_privileged:
        r += 25
    if u.admin_count and u.admin_count > 0:
        r += 15
    if u.password_never_expires:
        r += 10
    if u.pwd_last_set and u.pwd_last_set < _now() - timedelta(days=365):
        r += 15
    return min(100, r)


def _serialize(u: ADUser, base: int, reasons: list[str]) -> dict:
    return {
        "sam_account_name": u.sam_account_name,
        "display_name": u.display_name,
        "is_privileged": u.is_privileged,
        "admin_count": u.admin_count,
        "password_never_expires": u.password_never_expires,
        "pwd_last_set": u.pwd_last_set,
        "last_logon_timestamp": u.last_logon_timestamp,
        "spn": u.service_principal_name,
        "risk_score": _risk(u, base),
        "reasons": reasons,
    }


async def kerberoasting(session: AsyncSession) -> dict:
    """Contas de usuário com SPN — alvo de Kerberoasting (MITRE T1558.003)."""
    rows = (
        await session.execute(
            select(ADUser).where(and_(_spn_len_gt0(), ADUser.is_disabled.is_(False)))
            .order_by(ADUser.is_privileged.desc())
        )
    ).scalars().all()
    items = []
    for u in rows:
        reasons = ["Conta de usuário com SPN"]
        if u.is_privileged:
            reasons.append("Privilegiada — impacto alto se comprometida")
        if u.password_never_expires:
            reasons.append("Senha nunca expira")
        if u.pwd_last_set and u.pwd_last_set < _now() - timedelta(days=365):
            reasons.append("Senha não trocada há mais de 1 ano")
        items.append(_serialize(u, 45, reasons))
    return {
        "technique": "Kerberoasting (T1558.003)",
        "recommendation": "Use gMSA ou senhas longas (25+); evite SPN em contas de usuário privilegiadas.",
        "count": len(items),
        "items": sorted(items, key=lambda x: x["risk_score"], reverse=True),
    }


async def asrep_roasting(session: AsyncSession) -> dict:
    """Contas com DONT_REQ_PREAUTH — alvo de AS-REP Roasting (MITRE T1558.004)."""
    rows = (
        await session.execute(
            select(ADUser).where(
                and_(ADUser.dont_require_preauth.is_(True), ADUser.is_disabled.is_(False))
            )
        )
    ).scalars().all()
    items = []
    for u in rows:
        reasons = ["Pré-autenticação Kerberos desabilitada"]
        if u.is_privileged:
            reasons.append("Privilegiada")
        items.append(_serialize(u, 55, reasons))
    return {
        "technique": "AS-REP Roasting (T1558.004)",
        "recommendation": "Habilite a pré-autenticação Kerberos (remova DONT_REQ_PREAUTH).",
        "count": len(items),
        "items": sorted(items, key=lambda x: x["risk_score"], reverse=True),
    }


async def stale_admins(session: AsyncSession) -> dict:
    """Contas privilegiadas com risco de higiene: inativas, senha antiga,
    expiradas-ativas, nunca-expira ou password-not-required."""
    old_cut = _now() - timedelta(days=365)
    rows = (
        await session.execute(
            select(ADUser).where(
                and_(
                    ADUser.is_privileged.is_(True),
                    ADUser.is_disabled.is_(False),
                    or_(
                        ADUser.is_inactive.is_(True),
                        ADUser.password_never_expires.is_(True),
                        ADUser.password_not_required.is_(True),
                        and_(ADUser.pwd_last_set.is_not(None), ADUser.pwd_last_set < old_cut),
                        and_(ADUser.account_expires.is_not(None), ADUser.account_expires < _now()),
                    ),
                )
            )
        )
    ).scalars().all()
    items = []
    for u in rows:
        reasons = []
        if u.is_inactive:
            reasons.append("Privilegiada e inativa")
        if u.password_never_expires:
            reasons.append("Senha nunca expira")
        if u.password_not_required:
            reasons.append("Password Not Required")
        if u.pwd_last_set and u.pwd_last_set < old_cut:
            reasons.append("Senha não trocada há mais de 1 ano")
        if u.account_expires and u.account_expires < _now():
            reasons.append("Conta expirada ainda habilitada")
        items.append(_serialize(u, 50, reasons))
    return {
        "technique": "Higiene de contas privilegiadas",
        "recommendation": "Revise/rotacione ou desabilite contas administrativas ociosas ou mal configuradas.",
        "count": len(items),
        "items": sorted(items, key=lambda x: x["risk_score"], reverse=True),
    }


async def summary(session: AsyncSession) -> dict:
    k = await kerberoasting(session)
    a = await asrep_roasting(session)
    s = await stale_admins(session)
    return {
        "kerberoasting": k["count"],
        "asrep_roasting": a["count"],
        "stale_admins": s["count"],
    }
