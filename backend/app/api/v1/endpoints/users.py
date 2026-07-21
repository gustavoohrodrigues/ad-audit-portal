"""Endpoints de usuários AD: busca, detalhe, timeline, bloqueios, senha, grupos, risco."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_capability
from app.database import get_session
from app.models.directory import ADUser
from app.models.enums import EventType
from app.models.event import NormalizedEvent
from app.schemas import ADUserOut, EventOut

router = APIRouter(prefix="/users", tags=["users"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _resolve_user(session: AsyncSession, identifier: str) -> ADUser | None:
    stmt = select(ADUser).where(
        or_(
            ADUser.sam_account_name == identifier,
            ADUser.user_principal_name == identifier,
            ADUser.object_sid == identifier,
            ADUser.distinguished_name == identifier,
        )
    )
    return (await session.execute(stmt)).scalars().first()


@router.get("/search")
async def search_users(
    q: str = Query(min_length=1),
    limit: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    like = f"%{q}%"
    stmt = (
        select(ADUser)
        .where(
            or_(
                ADUser.sam_account_name.ilike(like),
                ADUser.display_name.ilike(like),
                ADUser.mail.ilike(like),
                ADUser.user_principal_name.ilike(like),
                ADUser.object_sid.ilike(like),
                ADUser.distinguished_name.ilike(like),
            )
        )
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [ADUserOut.model_validate(u) for u in rows],
    }


@router.get("/{identifier}", response_model=ADUserOut)
async def get_user(
    identifier: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> ADUserOut:
    u = await _resolve_user(session, identifier)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return ADUserOut.model_validate(u)


async def _events_for(
    session: AsyncSession, identifier: str, types: list[EventType] | None, limit: int
) -> list[NormalizedEvent]:
    stmt = select(NormalizedEvent).where(
        or_(
            NormalizedEvent.target_username == identifier,
            NormalizedEvent.target_sid == identifier,
            NormalizedEvent.target_upn == identifier,
        )
    )
    if types:
        stmt = stmt.where(NormalizedEvent.event_type.in_(types))
    stmt = stmt.order_by(NormalizedEvent.event_time_utc.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{identifier}/timeline", response_model=list[EventOut])
async def user_timeline(
    identifier: str,
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> list[EventOut]:
    u = await _resolve_user(session, identifier)
    key = u.sam_account_name if u else identifier
    rows = await _events_for(session, key, None, limit)
    return [EventOut.model_validate(e) for e in rows]


@router.get("/{identifier}/lockouts", response_model=list[EventOut])
async def user_lockouts(
    identifier: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("lockout:read")),
) -> list[EventOut]:
    u = await _resolve_user(session, identifier)
    key = u.sam_account_name if u else identifier
    rows = await _events_for(session, key, [EventType.account_lockout], 200)
    return [EventOut.model_validate(e) for e in rows]


@router.get("/{identifier}/password-events", response_model=list[EventOut])
async def user_password_events(
    identifier: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("password_event:read")),
) -> list[EventOut]:
    u = await _resolve_user(session, identifier)
    key = u.sam_account_name if u else identifier
    rows = await _events_for(
        session, key, [EventType.password_change, EventType.password_reset], 200
    )
    return [EventOut.model_validate(e) for e in rows]


@router.get("/{identifier}/group-history", response_model=list[EventOut])
async def user_group_history(
    identifier: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> list[EventOut]:
    u = await _resolve_user(session, identifier)
    key = u.sam_account_name if u else identifier
    rows = await _events_for(
        session,
        key,
        [EventType.group_member_added, EventType.group_member_removed],
        200,
    )
    return [EventOut.model_validate(e) for e in rows]


@router.get("/{identifier}/lockout-origin")
async def user_lockout_origin(
    identifier: str,
    live: bool = False,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("lockout:read")),
) -> dict:
    """Origem do bloqueio (Event 4740). Retorna dados coletados + comando PS pronto,
    e, se ``live=true`` e WinRM habilitado, consulta os DCs ao vivo."""
    from app.services import lockout_origin as lo

    u = await _resolve_user(session, identifier)
    username = u.sam_account_name if u else identifier

    db_results = await lo.from_database(session, username)
    live_results: list = []
    live_error = None
    if live:
        live_results, live_error = lo.from_winrm_live(username)

    return {
        "username": username,
        "powershell_command": lo.build_ps_command(username),
        "collected": db_results,
        "live": live_results,
        "live_error": live_error,
        "hint": (
            "Se não há dados coletados, copie o comando e rode em um DC (ou habilite "
            "WEF/WinRM). Properties[1] = computador de origem do bloqueio."
        ),
    }


@router.get("/{identifier}/risk")
async def user_risk(
    identifier: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> dict:
    u = await _resolve_user(session, identifier)
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    reasons = []
    if u.is_privileged:
        reasons.append("Conta privilegiada")
    if u.is_critical:
        reasons.append("Conta crítica")
    if u.password_never_expires:
        reasons.append("Senha nunca expira")
    if u.password_not_required:
        reasons.append("Password Not Required")
    if u.sid_history:
        reasons.append("Possui SIDHistory")
    if u.allowed_to_delegate_to:
        reasons.append("Delegação configurada")
    if u.service_principal_name:
        reasons.append("Possui SPN")
    if u.is_inactive:
        reasons.append("Conta inativa")
    return {
        "username": u.sam_account_name,
        "risk_score": u.risk_score,
        "reasons": reasons,
        "is_privileged": u.is_privileged,
        "is_critical": u.is_critical,
    }
