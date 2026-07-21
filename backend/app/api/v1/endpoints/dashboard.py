"""Endpoints do dashboard operacional (Dark Ops / NOC)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.dialects.postgresql import JSONB

from app.core.deps import CurrentUser, require_capability
from app.models.directory import ADComputer, ADGroup, ADUser, DomainController
from app.models.enums import AlertStatus, EventType, Severity
from app.models.event import NormalizedEvent
from app.models.ops import Alert, EventSource
from app.schemas import DashboardSummary, RankItem, TimeBucket
from app.database import get_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _count(session: AsyncSession, stmt) -> int:
    return (await session.execute(stmt)).scalar_one() or 0


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> DashboardSummary:
    now = _utcnow()
    d1, d7, d30 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)

    def ev_count(*types: EventType, since: datetime):
        return select(func.count()).select_from(NormalizedEvent).where(
            NormalizedEvent.event_type.in_(types),
            NormalizedEvent.event_time_utc >= since,
        )

    lockouts_24h = await _count(session, ev_count(EventType.account_lockout, since=d1))
    lockouts_7d = await _count(session, ev_count(EventType.account_lockout, since=d7))
    lockouts_30d = await _count(session, ev_count(EventType.account_lockout, since=d30))
    failed_24h = await _count(
        session,
        ev_count(
            EventType.failed_logon,
            EventType.kerberos_preauth_failed,
            EventType.ntlm_validation,
            since=d1,
        ),
    )
    pwd_24h = await _count(
        session,
        ev_count(EventType.password_change, EventType.password_reset, since=d1),
    )
    admin_changes = await _count(
        session,
        ev_count(
            EventType.account_changed,
            EventType.user_created,
            EventType.user_deleted,
            EventType.account_renamed,
            since=d1,
        ),
    )
    priv_group_changes = await _count(
        session,
        select(func.count()).select_from(NormalizedEvent).where(
            NormalizedEvent.event_type.in_(
                [EventType.group_member_added, EventType.group_member_removed]
            ),
            NormalizedEvent.is_privileged_target.is_(True),
            NormalizedEvent.event_time_utc >= d1,
        ),
    )

    async def alert_count(sev: Severity) -> int:
        return await _count(
            session,
            select(func.count()).select_from(Alert).where(
                Alert.severity == sev, Alert.status == AlertStatus.open
            ),
        )

    inactive = await _count(
        session,
        select(func.count()).select_from(ADUser).where(ADUser.is_inactive.is_(True)),
    )
    never_expire = await _count(
        session,
        select(func.count()).select_from(ADUser).where(
            ADUser.password_never_expires.is_(True)
        ),
    )
    privileged = await _count(
        session,
        select(func.count()).select_from(ADUser).where(ADUser.is_privileged.is_(True)),
    )
    ingested_24h = await _count(
        session,
        select(func.count()).select_from(NormalizedEvent).where(
            NormalizedEvent.ingested_at >= d1
        ),
    )

    # taxa de erro de ingestão
    total_ing = (
        await session.execute(select(func.coalesce(func.sum(EventSource.events_ingested), 0)))
    ).scalar_one()
    total_err = (
        await session.execute(select(func.coalesce(func.sum(EventSource.errors_count), 0)))
    ).scalar_one()
    err_rate = round(total_err / total_ing, 4) if total_ing else 0.0

    # rankings
    async def ranking(column, since, extra=None, filt=None) -> list[RankItem]:
        stmt = (
            select(column, func.count().label("c"))
            .where(NormalizedEvent.event_time_utc >= since)
            .group_by(column)
            .order_by(func.count().desc())
            .limit(10)
        )
        if filt is not None:
            stmt = stmt.where(filt)
        rows = (await session.execute(stmt)).all()
        return [RankItem(label=str(r[0] or "-"), count=r[1]) for r in rows]

    top_locked = await ranking(
        NormalizedEvent.target_username, d1,
        filt=NormalizedEvent.event_type == EventType.account_lockout,
    )
    top_sources = await ranking(
        NormalizedEvent.caller_computer, d1,
        filt=NormalizedEvent.event_type == EventType.account_lockout,
    )
    top_dcs = await ranking(NormalizedEvent.domain_controller, d1)

    # falhas por hora (24h)
    bucket = func.date_trunc("hour", NormalizedEvent.event_time_utc)
    stmt = (
        select(bucket.label("h"), func.count())
        .where(
            NormalizedEvent.event_type.in_(
                [EventType.failed_logon, EventType.kerberos_preauth_failed]
            ),
            NormalizedEvent.event_time_utc >= d1,
        )
        .group_by("h")
        .order_by("h")
    )
    fbh = [TimeBucket(ts=r[0], count=r[1]) for r in (await session.execute(stmt)).all()]

    return DashboardSummary(
        lockouts_24h=lockouts_24h,
        lockouts_7d=lockouts_7d,
        lockouts_30d=lockouts_30d,
        failed_logons_24h=failed_24h,
        password_events_24h=pwd_24h,
        admin_changes_24h=admin_changes,
        privileged_group_changes_24h=priv_group_changes,
        critical_alerts_open=await alert_count(Severity.critical),
        high_alerts_open=await alert_count(Severity.high),
        medium_alerts_open=await alert_count(Severity.medium),
        inactive_accounts=inactive,
        never_expire_accounts=never_expire,
        privileged_accounts=privileged,
        events_ingested_24h=ingested_24h,
        ingestion_error_rate=err_rate,
        top_locked_users=top_locked,
        top_source_computers=top_sources,
        top_domain_controllers=top_dcs,
        failed_logons_by_hour=fbh,
    )


@router.get("/security-score")
async def security_score(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    """Nota geral de postura de segurança do AD (0-100, maior=melhor). Cacheado."""
    from app.config import get_settings
    from app.core.cache import get_or_set
    from app.services.posture import compute_security_score

    async def _load() -> dict:
        return await compute_security_score(session)

    return await get_or_set(
        "score", "global", get_settings().cache_dashboard_ttl_seconds, _load
    )


@router.get("/security-score/history")
async def security_score_history(
    days: int = 90,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    from app.models.analytics import SecurityScoreHistory

    since = (_utcnow() - timedelta(days=days)).date()
    rows = (
        await session.execute(
            select(SecurityScoreHistory)
            .where(SecurityScoreHistory.snapshot_date >= since)
            .order_by(SecurityScoreHistory.snapshot_date)
        )
    ).scalars().all()
    return {
        "series": [
            {"date": str(r.snapshot_date), "score": r.score, "grade": r.grade}
            for r in rows
        ]
    }


@router.get("/posture-history")
async def posture_history(
    days: int = 90,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    from app.models.analytics import PostureHistory

    since = (_utcnow() - timedelta(days=days)).date()
    rows = (
        await session.execute(
            select(PostureHistory)
            .where(PostureHistory.snapshot_date >= since)
            .order_by(PostureHistory.snapshot_date)
        )
    ).scalars().all()
    return {"series": [{"date": str(r.snapshot_date), **r.counts} for r in rows]}


@router.get("/lockouts")
async def dashboard_lockouts(
    hours: int = 24,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    since = _utcnow() - timedelta(hours=hours)
    stmt = (
        select(NormalizedEvent)
        .where(
            NormalizedEvent.event_type == EventType.account_lockout,
            NormalizedEvent.event_time_utc >= since,
        )
        .order_by(NormalizedEvent.event_time_utc.desc())
        .limit(200)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": e.id,
                "time": e.event_time_utc,
                "user": e.target_username,
                "dc": e.domain_controller,
                "caller": e.caller_computer,
                "risk": e.risk_score,
            }
            for e in rows
        ],
    }


@router.get("/risk-events")
async def risk_events(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    stmt = (
        select(NormalizedEvent)
        .where(NormalizedEvent.risk_score >= 50)
        .order_by(NormalizedEvent.event_time_utc.desc())
        .limit(min(limit, 200))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "time": e.event_time_utc,
                "type": e.event_type,
                "severity": e.severity,
                "risk": e.risk_score,
                "user": e.target_username,
                "dc": e.domain_controller,
            }
            for e in rows
        ]
    }


@router.get("/domain-controllers")
async def domain_controllers(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    rows = (await session.execute(select(DomainController))).scalars().all()
    return {
        "items": [
            {
                "hostname": dc.hostname,
                "status": dc.status,
                "last_event_at": dc.last_event_at,
                "event_count_24h": dc.event_count_24h,
                "ingestion_lag_seconds": dc.ingestion_lag_seconds,
            }
            for dc in rows
        ]
    }


@router.get("/privileged-groups")
async def privileged_groups(
    hours: int = 168,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_capability("dashboard:read")),
) -> dict:
    since = _utcnow() - timedelta(hours=hours)
    stmt = (
        select(NormalizedEvent)
        .where(
            NormalizedEvent.event_type.in_(
                [EventType.group_member_added, EventType.group_member_removed]
            ),
            NormalizedEvent.is_privileged_target.is_(True),
            NormalizedEvent.event_time_utc >= since,
        )
        .order_by(NormalizedEvent.event_time_utc.desc())
        .limit(200)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "time": e.event_time_utc,
                "type": e.event_type,
                "target": e.target_username,
                "actor": e.actor_username,
                "dc": e.domain_controller,
                "risk": e.risk_score,
            }
            for e in rows
        ]
    }
