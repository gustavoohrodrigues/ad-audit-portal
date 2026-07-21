"""Inventário e postura de segurança de contas (baseado em ad_users sincronizado).

Somente leitura. Fornece contagens por categoria de risco e o drill-down das
contas de cada categoria.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, and_, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.directory import ADUser
from app.schemas import ADUserOut

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _spn_len():
    return func.jsonb_array_length(func.cast(ADUser.service_principal_name, JSONB))


def _deleg_len():
    return func.jsonb_array_length(func.cast(ADUser.allowed_to_delegate_to, JSONB))


def _sidhist_len():
    return func.jsonb_array_length(func.cast(ADUser.sid_history, JSONB))


def _now():
    return datetime.now(timezone.utc)


# Cada categoria -> (rótulo, condição SQLAlchemy, severidade sugerida)
def _categories():
    return {
        "inactive": ("Contas inativas", ADUser.is_inactive.is_(True), "medium"),
        "never_expires": (
            "Senha nunca expira",
            ADUser.password_never_expires.is_(True),
            "medium",
        ),
        "password_not_required": (
            "Password Not Required",
            ADUser.password_not_required.is_(True),
            "high",
        ),
        "privileged": ("Contas privilegiadas", ADUser.is_privileged.is_(True), "high"),
        "admin_count": (
            "adminCount = 1",
            func.coalesce(ADUser.admin_count, 0) > 0,
            "high",
        ),
        "spn": ("Contas com SPN", _spn_len() > 0, "medium"),
        "delegation": ("Delegação Kerberos", _deleg_len() > 0, "high"),
        "sid_history": ("Com SIDHistory", _sidhist_len() > 0, "high"),
        "expired_enabled": (
            "Expiradas ainda habilitadas",
            and_(
                ADUser.account_expires.is_not(None),
                ADUser.account_expires < _now(),
                ADUser.is_disabled.is_(False),
            ),
            "medium",
        ),
        "disabled": ("Contas desabilitadas", ADUser.is_disabled.is_(True), "low"),
        "locked": ("Contas bloqueadas", ADUser.is_locked.is_(True), "high"),
        "critical": ("Contas críticas", ADUser.is_critical.is_(True), "critical"),
    }


@router.get("/summary")
async def inventory_summary(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    total = (await session.execute(select(func.count()).select_from(ADUser))).scalar_one()
    cats = _categories()
    items = []
    for key, (label, cond, sev) in cats.items():
        count = (
            await session.execute(
                select(func.count()).select_from(ADUser).where(cond)
            )
        ).scalar_one()
        items.append({"key": key, "label": label, "count": count, "severity": sev})
    # ordena por severidade e contagem
    sev_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    items.sort(key=lambda x: (sev_rank.get(x["severity"], 0), x["count"]), reverse=True)
    return {"total_accounts": total, "categories": items}


@router.get("/accounts")
async def inventory_accounts(
    category: str = Query(..., description="chave da categoria"),
    q: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    cats = _categories()
    if category not in cats:
        raise HTTPException(status_code=404, detail="Categoria desconhecida")
    label, cond, sev = cats[category]
    stmt = select(ADUser).where(cond)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            ADUser.sam_account_name.ilike(like) | ADUser.display_name.ilike(like)
        )
    stmt = stmt.order_by(ADUser.risk_score.desc(), ADUser.sam_account_name).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "category": category,
        "label": label,
        "severity": sev,
        "count": len(rows),
        "items": [ADUserOut.model_validate(u) for u in rows],
    }
