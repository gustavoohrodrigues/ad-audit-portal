"""Geração e despacho de alertas com deduplicação e supressão.

Cria alertas para eventos de alto risco, deduplica por (tipo+alvo+janela) e
despacha para os canais habilitados (e-mail, webhook, GLPI). Cria ticket GLPI
apenas para severidade crítica, respeitando janela anti-duplicidade.
"""
from __future__ import annotations

import hashlib
import json
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import httpx
from sqlalchemy import text

from app.celery_app import celery_app
from app.config import config
from app.db import session_scope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dedup_key(event_type: str, target: str, severity: str, when: datetime) -> str:
    bucket = int(when.timestamp() // (config.dedup_window_min * 60))
    raw = f"{event_type}:{target}:{severity}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@celery_app.task(name="app.tasks.alerts.evaluate_and_dispatch")
def evaluate_and_dispatch() -> dict:
    if not config.alerts_enabled:
        return {"skipped": True}
    since = _utcnow() - timedelta(minutes=config.dedup_window_min)
    created, dispatched = 0, 0

    with session_scope() as s:
        candidates = s.execute(
            text(
                """
                SELECT id, event_type, target_username, severity, risk_score,
                       event_time_utc, domain_controller
                FROM normalized_events
                WHERE risk_score >= :th AND event_time_utc >= :since
                ORDER BY risk_score DESC LIMIT 500
                """
            ),
            {"th": config.th_medium, "since": since},
        ).fetchall()

        for (eid, etype, target, sev, score, etime, dc) in candidates:
            key = _dedup_key(etype, target or "-", sev, etime)
            exists = s.execute(
                text("SELECT id FROM alerts WHERE dedup_key = :k"), {"k": key}
            ).first()
            if exists:
                continue
            title = f"[{sev.upper()}] {etype} — {target or 'n/d'}"
            ctx = {"event_id": eid, "dc": dc, "risk_score": score, "type": etype}
            row = s.execute(
                text(
                    """
                    INSERT INTO alerts (title, description, severity, risk_score,
                        status, target_username, dedup_key, event_id, context,
                        notified_channels, created_at, updated_at)
                    VALUES (:t,:d,:sev,:score,'open',:target,:key,:eid,
                        CAST(:ctx AS JSONB), CAST('[]' AS JSONB), :now,:now)
                    RETURNING id
                    """
                ),
                {
                    "t": title, "d": f"Evento de risco {score} em {dc}.",
                    "sev": sev, "score": score, "target": target, "key": key,
                    "eid": eid, "ctx": json.dumps(ctx), "now": _utcnow(),
                },
            ).first()
            alert_id = row[0]
            created += 1
            channels = _dispatch(sev, title, ctx, target)
            if channels:
                s.execute(
                    text("UPDATE alerts SET notified_channels=CAST(:c AS JSONB) WHERE id=:id"),
                    {"c": json.dumps(channels), "id": alert_id},
                )
                dispatched += 1
            if sev == "critical" and config.glpi_enabled and config.glpi_on_critical:
                _maybe_glpi_ticket(s, alert_id, title, ctx, target)

    return {"created": created, "dispatched": dispatched}


def _dispatch(severity: str, title: str, ctx: dict, target: str | None) -> list[str]:
    channels: list[str] = []
    body = f"{title}\nDetalhes: {json.dumps(ctx, ensure_ascii=False)}\nAlvo: {target}"
    if config.email_enabled and config.smtp_to:
        try:
            _send_email(title, body)
            channels.append("email")
        except Exception:  # noqa: BLE001
            pass
    if config.webhook_enabled and config.webhook_url:
        try:
            headers = {"Content-Type": "application/json"}
            if config.webhook_token:
                headers["Authorization"] = f"Bearer {config.webhook_token}"
            httpx.post(
                config.webhook_url,
                json={"title": title, "severity": severity, "context": ctx, "target": target},
                headers=headers, timeout=10, verify=True,
            )
            channels.append("webhook")
        except Exception:  # noqa: BLE001
            pass
    return channels


def _send_email(subject: str, body: str) -> None:
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = f"[AD-Audit] {subject}"
    msg["From"] = config.smtp_from
    msg["To"] = ", ".join(config.smtp_to)
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as server:
        if config.smtp_tls:
            server.starttls()
        if config.smtp_user:
            server.login(config.smtp_user, config.smtp_pass)
        server.sendmail(config.smtp_from, config.smtp_to, msg.as_string())


def _maybe_glpi_ticket(session, alert_id: int, title: str, ctx: dict, target: str | None) -> None:
    """Cria ticket GLPI para crítico, evitando duplicidade na janela configurada."""
    recent = session.execute(
        text(
            """
            SELECT id FROM ticket_links
            WHERE system='glpi' AND created_at >= :since
              AND ticket_url LIKE :like
            LIMIT 1
            """
        ),
        {"since": _utcnow() - timedelta(hours=config.glpi_dedup_h), "like": f"%{target}%"},
    ).first()
    if recent:
        return
    try:
        with httpx.Client(verify=True, timeout=15) as client:
            init = client.get(
                f"{config.glpi_url}/apirest.php/initSession",
                headers={
                    "App-Token": config.glpi_app_token,
                    "Authorization": f"user_token {config.glpi_user_token}",
                },
            )
            init.raise_for_status()
            sess_token = init.json().get("session_token")
            headers = {
                "App-Token": config.glpi_app_token,
                "Session-Token": sess_token,
                "Content-Type": "application/json",
            }
            payload = {
                "input": {
                    "name": title,
                    "content": json.dumps(ctx, ensure_ascii=False),
                    "urgency": 5, "impact": 5, "priority": 5,
                    "entities_id": config.glpi_entity,
                    "type": 1,
                }
            }
            resp = client.post(
                f"{config.glpi_url}/apirest.php/Ticket", headers=headers, json=payload
            )
            resp.raise_for_status()
            ticket_id = resp.json().get("id")
            ticket_url = f"{config.glpi_url}/front/ticket.form.php?id={ticket_id}"
            session.execute(
                text(
                    """
                    INSERT INTO ticket_links (system, ticket_number, ticket_url,
                        created_by, created_at)
                    VALUES ('glpi', :num, :url, 'worker:auto', :now)
                    """
                ),
                {"num": str(ticket_id), "url": ticket_url, "now": _utcnow()},
            )
            client.get(f"{config.glpi_url}/apirest.php/killSession", headers=headers)
    except Exception:  # noqa: BLE001
        return
