"""Recalcula risco/severidade de eventos recentes ainda não pontuados."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.celery_app import celery_app
from app.config import config
from app.db import session_scope
from app.scoring import score_event


@celery_app.task(name="app.tasks.risk.recompute_recent_risk")
def recompute_recent_risk() -> dict:
    if not config.risk_scoring_enabled:
        return {"skipped": True}
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    updated = 0
    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT id, event_type, event_time_utc, is_privileged_target,
                       is_critical_account, target_username
                FROM normalized_events
                WHERE event_time_utc >= :since AND (risk_score = 0 OR risk_score IS NULL)
                LIMIT 5000
                """
            ),
            {"since": since},
        ).fetchall()

        for (eid, etype, etime, priv, crit, user) in rows:
            recurring = 0
            if etype == "account_lockout" and user:
                recurring = s.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM normalized_events
                        WHERE target_username=:u AND event_type='account_lockout'
                          AND event_time_utc >= :w
                        """
                    ),
                    {"u": user, "w": etime - timedelta(hours=config.recurring_lockout_window_h)},
                ).scalar_one()

            is_priv_group = etype in ("group_member_added", "group_member_removed") and bool(priv)
            score, sev = score_event(
                event_type=etype,
                event_time=etime,
                is_privileged_target=bool(priv),
                is_critical_account=bool(crit),
                privileged_group_change=is_priv_group,
                recurring_lockouts=recurring,
            )
            s.execute(
                text(
                    "UPDATE normalized_events SET risk_score=:r, severity=:s, updated_at=:now WHERE id=:id"
                ),
                {"r": score, "s": sev, "now": datetime.now(timezone.utc), "id": eid},
            )
            updated += 1
    return {"updated": updated}
