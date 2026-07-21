"""Correlação de eventos e saúde das fontes.

Para cada bloqueio (4740), correlaciona falhas de autenticação (4625/4771/4776)
do mesmo alvo dentro da janela, conta bloqueios recentes do usuário e da mesma
origem, e atualiza/insere a investigação de bloqueio.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.celery_app import celery_app
from app.config import config
from app.db import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.correlation.correlate_recent")
def correlate_recent() -> dict:
    window = timedelta(minutes=config.lockout_window_min)
    since = _utcnow() - timedelta(hours=config.recurring_lockout_window_h)
    created, updated = 0, 0

    with session_scope() as s:
        lockouts = s.execute(
            text(
                """
                SELECT e.id, e.target_username, e.target_sid, e.event_time_utc,
                       e.domain_controller, e.caller_computer, e.source_ip,
                       e.authentication_package
                FROM normalized_events e
                WHERE e.event_type = 'account_lockout'
                  AND e.event_time_utc >= :since
                """
            ),
            {"since": since},
        ).fetchall()

        for lk in lockouts:
            (eid, user, sid, etime, dc, caller, sip, auth) = lk
            win_start = etime - window

            correlated = s.execute(
                text(
                    """
                    SELECT id FROM normalized_events
                    WHERE target_username = :user
                      AND event_type IN ('failed_logon','kerberos_preauth_failed','ntlm_validation')
                      AND event_time_utc BETWEEN :ws AND :we
                    ORDER BY event_time_utc DESC LIMIT 50
                    """
                ),
                {"user": user, "ws": win_start, "we": etime},
            ).fetchall()
            correlated_ids = [r[0] for r in correlated]

            lockouts_24h = s.execute(
                text(
                    """
                    SELECT COUNT(*) FROM normalized_events
                    WHERE target_username = :user AND event_type='account_lockout'
                      AND event_time_utc >= :since
                    """
                ),
                {"user": user, "since": etime - timedelta(hours=24)},
            ).scalar_one()

            same_source = 0
            if caller:
                same_source = s.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM normalized_events
                        WHERE caller_computer = :caller AND event_type='account_lockout'
                          AND event_time_utc >= :since
                        """
                    ),
                    {"caller": caller, "since": etime - timedelta(hours=24)},
                ).scalar_one()

            corr_id = str(uuid.uuid4())
            s.execute(
                text(
                    "UPDATE normalized_events SET correlation_id=:c WHERE id = ANY(:ids)"
                ),
                {"c": corr_id, "ids": correlated_ids + [eid]},
            )

            existing = s.execute(
                text("SELECT id FROM lockout_investigations WHERE event_id = :eid"),
                {"eid": eid},
            ).first()
            auth_type = "Kerberos" if (auth or "").lower().startswith("kerberos") else (
                "NTLM" if auth else None
            )
            if existing:
                s.execute(
                    text(
                        """
                        UPDATE lockout_investigations
                        SET lockouts_24h=:l24, lockouts_same_source=:lss,
                            correlated_event_ids=CAST(:cids AS JSONB), updated_at=:now
                        WHERE id=:id
                        """
                    ),
                    {
                        "l24": lockouts_24h, "lss": same_source,
                        "cids": _json(correlated_ids), "now": _utcnow(),
                        "id": existing[0],
                    },
                )
                updated += 1
            else:
                s.execute(
                    text(
                        """
                        INSERT INTO lockout_investigations (
                            event_id, target_username, target_sid, lockout_time_utc,
                            domain_controller, caller_computer, source_ip, auth_type,
                            lockouts_24h, lockouts_same_source, correlated_event_ids,
                            status, created_at, updated_at)
                        VALUES (:eid,:user,:sid,:etime,:dc,:caller,:sip,:auth,
                            :l24,:lss,CAST(:cids AS JSONB),'new',:now,:now)
                        """
                    ),
                    {
                        "eid": eid, "user": user, "sid": sid, "etime": etime,
                        "dc": dc, "caller": caller, "sip": sip, "auth": auth_type,
                        "l24": lockouts_24h, "lss": same_source,
                        "cids": _json(correlated_ids), "now": _utcnow(),
                    },
                )
                created += 1

    return {"lockouts": len(lockouts), "created": created, "updated": updated}


@celery_app.task(name="app.tasks.correlation.refresh_source_health")
def refresh_source_health() -> dict:
    """Atualiza contagem 24h, último evento e lag de ingestão por DC."""
    now = _utcnow()
    d1 = now - timedelta(days=1)
    with session_scope() as s:
        dcs = s.execute(
            text("SELECT DISTINCT domain_controller FROM normalized_events")
        ).fetchall()
        for (dc,) in dcs:
            row = s.execute(
                text(
                    """
                    SELECT COUNT(*), MAX(event_time_utc), MAX(ingested_at)
                    FROM normalized_events
                    WHERE domain_controller = :dc AND event_time_utc >= :d1
                    """
                ),
                {"dc": dc, "d1": d1},
            ).first()
            count, last_evt, last_ing = row
            lag = int((now - last_evt).total_seconds()) if last_evt else None
            status = "healthy"
            if lag is None or lag > 3600:
                status = "degraded"
            if lag is not None and lag > 21600:
                status = "down"
            s.execute(
                text(
                    """
                    INSERT INTO domain_controllers (hostname, status, last_event_at,
                        last_heartbeat_at, event_count_24h, ingestion_lag_seconds, updated_at)
                    VALUES (:dc,:st,:le,:hb,:cnt,:lag,:hb)
                    ON CONFLICT (hostname) DO UPDATE SET
                        status=EXCLUDED.status, last_event_at=EXCLUDED.last_event_at,
                        last_heartbeat_at=EXCLUDED.last_heartbeat_at,
                        event_count_24h=EXCLUDED.event_count_24h,
                        ingestion_lag_seconds=EXCLUDED.ingestion_lag_seconds,
                        updated_at=EXCLUDED.updated_at
                    """
                ),
                {"dc": dc, "st": status, "le": last_evt, "hb": now, "cnt": count, "lag": lag},
            )
    return {"dcs": len(dcs)}


def _json(obj) -> str:
    import json

    return json.dumps(obj)
