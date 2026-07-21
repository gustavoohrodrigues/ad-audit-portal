"""Endpoints de grupos do AD (sincronizados). Somente leitura."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.directory import ADGroup

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("")
async def list_groups(
    q: str | None = None,
    privileged: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    stmt = select(ADGroup)
    if privileged is not None:
        stmt = stmt.where(ADGroup.is_privileged.is_(privileged))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(ADGroup.sam_account_name.ilike(like), ADGroup.display_name.ilike(like))
        )
    stmt = stmt.order_by(ADGroup.is_privileged.desc(), ADGroup.member_count.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    total = (await session.execute(select(func.count()).select_from(ADGroup))).scalar_one()
    priv = (
        await session.execute(
            select(func.count()).select_from(ADGroup).where(ADGroup.is_privileged.is_(True))
        )
    ).scalar_one()
    return {
        "total": total,
        "privileged_total": priv,
        "count": len(rows),
        "items": [
            {
                "sam_account_name": g.sam_account_name,
                "display_name": g.display_name,
                "description": g.description,
                "member_count": g.member_count,
                "is_privileged": g.is_privileged,
                "admin_count": g.admin_count,
            }
            for g in rows
        ],
    }


@router.get("/{sam}")
async def get_group(
    sam: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    g = (
        await session.execute(select(ADGroup).where(ADGroup.sam_account_name == sam))
    ).scalars().first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    import re

    members = [
        (m.group(1) if (m := re.match(r"CN=([^,]+)", dn)) else dn) for dn in g.members
    ]
    return {
        "sam_account_name": g.sam_account_name,
        "display_name": g.display_name,
        "description": g.description,
        "distinguished_name": g.distinguished_name,
        "is_privileged": g.is_privileged,
        "member_count": g.member_count,
        "members": members,
    }
