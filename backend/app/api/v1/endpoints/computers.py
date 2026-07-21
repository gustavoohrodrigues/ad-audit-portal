"""Endpoints de computadores do AD (sincronizados). Somente leitura."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.directory import ADComputer

router = APIRouter(prefix="/computers", tags=["computers"])


@router.get("")
async def list_computers(
    q: str | None = None,
    os: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    stmt = select(ADComputer)
    if os is not None:
        # filtro exato por SO (usado ao clicar numa barra do gráfico).
        # "Desconhecido" mapeia para registros sem SO preenchido.
        if os == "Desconhecido":
            stmt = stmt.where(ADComputer.operating_system.is_(None))
        else:
            stmt = stmt.where(ADComputer.operating_system == os)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ADComputer.sam_account_name.ilike(like),
                ADComputer.dns_host_name.ilike(like),
                ADComputer.operating_system.ilike(like),
            )
        )
    stmt = stmt.order_by(ADComputer.last_logon_timestamp.desc().nullslast()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    total = (
        await session.execute(select(func.count()).select_from(ADComputer))
    ).scalar_one()
    # distribuição por SO
    os_rows = (
        await session.execute(
            select(ADComputer.operating_system, func.count())
            .group_by(ADComputer.operating_system)
            .order_by(func.count().desc())
        )
    ).all()
    return {
        "total": total,
        "os_distribution": [
            {"os": (r[0] or "Desconhecido"), "count": r[1]} for r in os_rows
        ],
        "count": len(rows),
        "items": [
            {
                "sam_account_name": c.sam_account_name,
                "dns_host_name": c.dns_host_name,
                "operating_system": c.operating_system,
                "last_logon_timestamp": c.last_logon_timestamp,
                "when_created": c.when_created,
                "is_disabled": c.is_disabled,
            }
            for c in rows
        ],
    }
