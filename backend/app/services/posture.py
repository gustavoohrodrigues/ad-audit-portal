"""Cálculo de postura: Security Score do AD e contagens por categoria de risco.

Fonte única de verdade compartilhada entre o endpoint do dashboard e o snapshot
diário (histórico). Somente leitura.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.directory import ADComputer, ADUser

LEGACY_OS = ["%windows 7%", "%windows 8%", "%windows xp%", "%vista%",
             "%server 2003%", "%server 2008%"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _count(session: AsyncSession, model, cond) -> int:
    return (
        await session.execute(select(func.count()).select_from(model).where(cond))
    ).scalar_one()


def _arr_len_gt0(col):
    return func.jsonb_array_length(func.cast(col, JSONB)) > 0


async def compute_posture_counts(session: AsyncSession) -> dict[str, int]:
    """Contagens usadas na Postura e no histórico."""
    u = ADUser
    return {
        "total_users": await _count(session, u, u.id.is_not(None)),
        "inactive": await _count(session, u, and_(u.is_inactive.is_(True), u.is_disabled.is_(False))),
        "never_expires": await _count(session, u, u.password_never_expires.is_(True)),
        "password_not_required": await _count(session, u, u.password_not_required.is_(True)),
        "privileged": await _count(session, u, u.is_privileged.is_(True)),
        "admin_count": await _count(session, u, func.coalesce(u.admin_count, 0) > 0),
        "spn": await _count(session, u, _arr_len_gt0(u.service_principal_name)),
        "delegation": await _count(session, u, _arr_len_gt0(u.allowed_to_delegate_to)),
        "sid_history": await _count(session, u, _arr_len_gt0(u.sid_history)),
        "asrep": await _count(session, u, u.dont_require_preauth.is_(True)),
        "disabled": await _count(session, u, u.is_disabled.is_(True)),
        "locked": await _count(session, u, u.is_locked.is_(True)),
        "critical": await _count(session, u, u.is_critical.is_(True)),
        "legacy_machines": await _count(
            session, ADComputer, or_(*[ADComputer.operating_system.ilike(p) for p in LEGACY_OS])
        ),
    }


def score_from_counts(c: dict[str, int]) -> dict:
    """Parte pura do cálculo do score (testável sem banco)."""
    total_users = c.get("total_users", 0) or 1
    factors: list[dict] = []
    score = 100.0

    def penalize(label: str, count: int, per: float, cap: float, severity: str):
        nonlocal score
        impact = round(min(count * per, cap), 1)
        score -= impact
        if count > 0:
            factors.append({"label": label, "count": count, "impact": -impact, "severity": severity})

    penalize("Contas com Password Not Required", c.get("password_not_required", 0), 10, 20, "critical")
    penalize("Contas AS-REP roastable (sem pré-auth)", c.get("asrep", 0), 8, 16, "critical")
    penalize("Contas com SIDHistory", c.get("sid_history", 0), 5, 15, "high")
    penalize("Contas com delegação Kerberos", c.get("delegation", 0), 3, 12, "high")
    penalize("Senha nunca expira", c.get("never_expires", 0), 0.25, 15, "medium")
    penalize("Contas inativas ainda habilitadas", c.get("inactive", 0), 0.2, 12, "medium")
    penalize("Máquinas com SO legado/sem suporte", c.get("legacy_machines", 0), 0.05, 18, "high")
    if c.get("privileged", 0) / total_users > 0.03:
        penalize("Excesso de contas privilegiadas", c.get("privileged", 0), 0.1, 12, "high")

    score = max(0, round(score))
    grade = ("A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70
             else "D" if score >= 60 else "F")
    factors.sort(key=lambda f: f["impact"])
    return {"score": score, "grade": grade, "factors": factors}


async def compute_security_score(session: AsyncSession) -> dict:
    """Nota 0–100 (maior = melhor) com detalhamento dos fatores."""
    c = await compute_posture_counts(session)
    result = score_from_counts(c)
    result["computed_from"] = {
        "users": c["total_users"],
        "computers": await _count(session, ADComputer, ADComputer.id.is_not(None)),
        "privileged": c["privileged"], "spn_accounts": c["spn"],
        "legacy_machines": c["legacy_machines"], "asrep": c["asrep"],
    }
    return result


async def snapshot_daily(session: AsyncSession) -> dict:
    """Grava o snapshot do dia (idempotente por data) em history."""
    from app.models.analytics import PostureHistory, SecurityScoreHistory

    today = _now().date()
    score = await compute_security_score(session)
    counts = await compute_posture_counts(session)

    existing = (
        await session.execute(
            select(SecurityScoreHistory).where(SecurityScoreHistory.snapshot_date == today)
        )
    ).scalars().first()
    if existing:
        existing.score = score["score"]
        existing.grade = score["grade"]
        existing.factors = score["factors"]
        existing.computed_from = score["computed_from"]
    else:
        session.add(SecurityScoreHistory(
            snapshot_date=today, score=score["score"], grade=score["grade"],
            factors=score["factors"], computed_from=score["computed_from"],
        ))

    p_existing = (
        await session.execute(
            select(PostureHistory).where(PostureHistory.snapshot_date == today)
        )
    ).scalars().first()
    if p_existing:
        p_existing.counts = counts
    else:
        session.add(PostureHistory(snapshot_date=today, counts=counts))

    await session.commit()
    return {"date": str(today), "score": score["score"], "grade": score["grade"]}
