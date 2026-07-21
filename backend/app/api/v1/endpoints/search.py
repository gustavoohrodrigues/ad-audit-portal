"""Busca global (command palette / Ctrl+K). Somente leitura, respeita RBAC."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.directory import ADComputer, ADGroup, ADUser

router = APIRouter(prefix="/search", tags=["search"])

# Páginas navegáveis (filtradas por capacidade no cliente também).
PAGES = [
    {"label": "Dashboard", "path": "/"},
    {"label": "Saúde", "path": "/health"},
    {"label": "Postura de Segurança", "path": "/posture"},
    {"label": "Superfície de Ataque", "path": "/attack-surface"},
    {"label": "Grupos", "path": "/groups"},
    {"label": "Computadores", "path": "/computers"},
    {"label": "Watchlists", "path": "/watchlists"},
    {"label": "Bloqueios", "path": "/lockouts"},
    {"label": "Eventos", "path": "/events"},
    {"label": "Alertas", "path": "/alerts"},
    {"label": "Notificações", "path": "/notifications"},
    {"label": "Relatórios", "path": "/reports"},
    {"label": "Integrações", "path": "/integrations"},
    {"label": "Admin", "path": "/admin"},
    {"label": "Minha Conta / MFA", "path": "/account"},
]


@router.get("")
async def global_search(
    q: str = Query(min_length=1),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    from app.config import get_settings
    from app.core.cache import get_or_set

    settings = get_settings()

    async def _load() -> dict:
        return await _do_search(session, q)

    return await get_or_set("search", q.strip().lower(), settings.cache_search_ttl_seconds, _load)


async def _do_search(session: AsyncSession, q: str) -> dict:
    like = f"%{q}%"
    ql = q.lower()

    users = (
        await session.execute(
            select(ADUser).where(
                or_(
                    ADUser.sam_account_name.ilike(like),
                    ADUser.display_name.ilike(like),
                    ADUser.mail.ilike(like),
                    ADUser.user_principal_name.ilike(like),
                )
            ).limit(8)
        )
    ).scalars().all()
    groups = (
        await session.execute(
            select(ADGroup).where(
                or_(ADGroup.sam_account_name.ilike(like), ADGroup.display_name.ilike(like))
            ).limit(6)
        )
    ).scalars().all()
    computers = (
        await session.execute(
            select(ADComputer).where(
                or_(ADComputer.sam_account_name.ilike(like), ADComputer.dns_host_name.ilike(like))
            ).limit(6)
        )
    ).scalars().all()
    pages = [p for p in PAGES if ql in p["label"].lower()]

    return {
        "users": [
            {"label": u.sam_account_name, "sub": u.display_name, "path": f"/users/{u.sam_account_name}",
             "privileged": u.is_privileged}
            for u in users
        ],
        "groups": [
            {"label": g.sam_account_name, "sub": g.display_name, "path": "/groups",
             "privileged": g.is_privileged}
            for g in groups
        ],
        "computers": [
            {"label": c.sam_account_name, "sub": c.operating_system, "path": "/computers"}
            for c in computers
        ],
        "pages": pages,
    }
