"""Endpoints de eventos. Acesso ao JSON bruto exige capacidade 'event:raw_read'
(por padrão apenas security_analyst/administrator) e é auditado."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_capability
from app.core.metrics import events_query_total, raw_event_access_total
from app.database import get_session
from app.models.event import NormalizedEvent
from app.schemas import EventOut, EventRawOut, PaginatedEvents
from app.services.audit import record_audit

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PaginatedEvents)
async def list_events(
    q: str | None = None,
    event_id: int | None = None,
    event_type: str | None = None,
    target_username: str | None = None,
    domain_controller: str | None = None,
    caller_computer: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_risk: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> PaginatedEvents:
    events_query_total.labels(kind="list").inc()
    conds = []
    if event_id is not None:
        conds.append(NormalizedEvent.event_id == event_id)
    if event_type:
        conds.append(NormalizedEvent.event_type == event_type)
    if target_username:
        conds.append(NormalizedEvent.target_username.ilike(f"%{target_username}%"))
    if domain_controller:
        conds.append(NormalizedEvent.domain_controller == domain_controller)
    if caller_computer:
        conds.append(NormalizedEvent.caller_computer.ilike(f"%{caller_computer}%"))
    if date_from:
        conds.append(NormalizedEvent.event_time_utc >= date_from)
    if date_to:
        conds.append(NormalizedEvent.event_time_utc <= date_to)
    if min_risk is not None:
        conds.append(NormalizedEvent.risk_score >= min_risk)
    if q:
        like = f"%{q}%"
        conds.append(
            NormalizedEvent.target_username.ilike(like)
            | NormalizedEvent.target_upn.ilike(like)
            | NormalizedEvent.caller_computer.ilike(like)
            | NormalizedEvent.target_sid.ilike(like)
        )

    base = select(NormalizedEvent)
    for c in conds:
        base = base.where(c)

    total = (
        await session.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = (
        await session.execute(
            base.order_by(NormalizedEvent.event_time_utc.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return PaginatedEvents(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventOut.model_validate(e) for e in rows],
    )


@router.get("/{event_pk}", response_model=EventOut)
async def get_event(
    event_pk: int,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("user:read_basic")),
) -> EventOut:
    ev = await session.get(NormalizedEvent, event_pk)
    if not ev:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return EventOut.model_validate(ev)


@router.get("/{event_pk}/raw", response_model=EventRawOut)
async def get_event_raw(
    event_pk: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("event:raw_read")),
) -> EventRawOut:
    """Acesso ao JSON bruto — auditado (AUDIT_RAW_EVENT_ACCESS_SECURITY_ONLY)."""
    ev = await session.get(NormalizedEvent, event_pk)
    if not ev:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    raw_event_access_total.inc()
    await record_audit(
        session,
        actor=user.username,
        actor_role=user.role,
        action="raw_access",
        resource=f"event:{event_pk}",
        ip_address=request.client.host if request.client else None,
    )
    return EventRawOut.model_validate(ev)
