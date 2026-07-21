"""Configuração do worker (lê o mesmo .env; foco em risco, alertas, retenção)."""
from __future__ import annotations

import os


def _env(k: str, d: str = "") -> str:
    return os.getenv(k, d)


def _bool(k: str, d: bool = False) -> bool:
    return _env(k, str(d)).lower() in ("1", "true", "yes", "on")


def _int(k: str, d: int) -> int:
    try:
        return int(_env(k, str(d)))
    except ValueError:
        return d


def _csv(k: str) -> list[str]:
    return [x.strip() for x in _env(k).split(",") if x.strip()]


class WorkerConfig:
    database_url_sync = _env("DATABASE_URL").replace(
        "postgresql+psycopg://", "postgresql+psycopg://"
    )
    timezone = _env("APP_TIMEZONE", "America/Sao_Paulo")

    # correlação
    lockout_window_min = _int("LOCKOUT_CORRELATION_WINDOW_MINUTES", 30)
    failed_logon_window_min = _int("FAILED_LOGON_CORRELATION_WINDOW_MINUTES", 15)
    recurring_lockout_threshold = _int("RECURRING_LOCKOUT_THRESHOLD", 3)
    recurring_lockout_window_h = _int("RECURRING_LOCKOUT_WINDOW_HOURS", 24)

    # risco
    risk_scoring_enabled = _bool("RISK_SCORING_ENABLED", True)
    th_medium = _int("RISK_ALERT_THRESHOLD_MEDIUM", 50)
    th_high = _int("RISK_ALERT_THRESHOLD_HIGH", 75)
    th_critical = _int("RISK_ALERT_THRESHOLD_CRITICAL", 90)
    business_start = _int("BUSINESS_HOURS_START", 8)
    business_end = _int("BUSINESS_HOURS_END", 18)
    privileged_groups = [g.lower() for g in _csv("PRIVILEGED_GROUPS")]
    critical_users = [u.lower() for u in _csv("CRITICAL_USERS")]

    # alertas / integrações
    alerts_enabled = _bool("ALERTS_ENABLED", True)
    dedup_window_min = _int("ALERT_DEDUP_WINDOW_MINUTES", 60)
    email_enabled = _bool("ALERT_EMAIL_ENABLED", False)
    smtp_host = _env("SMTP_HOST")
    smtp_port = _int("SMTP_PORT", 587)
    smtp_user = _env("SMTP_USERNAME")
    smtp_pass = _env("SMTP_PASSWORD")
    smtp_from = _env("SMTP_FROM")
    smtp_to = _csv("SMTP_TO")
    smtp_tls = _bool("SMTP_USE_TLS", True)
    webhook_enabled = _bool("WEBHOOK_ENABLED", False)
    webhook_url = _env("WEBHOOK_URL")
    webhook_token = _env("WEBHOOK_TOKEN")
    glpi_enabled = _bool("GLPI_ENABLED", False)
    glpi_url = _env("GLPI_URL")
    glpi_app_token = _env("GLPI_APP_TOKEN")
    glpi_user_token = _env("GLPI_USER_TOKEN")
    glpi_entity = _int("GLPI_ENTITY_ID", 0)
    glpi_on_critical = _bool("GLPI_CREATE_TICKET_ON_CRITICAL", True)
    glpi_dedup_h = _int("GLPI_DEDUP_WINDOW_HOURS", 24)

    # retenção
    event_retention_days = _int("EVENT_RETENTION_DAYS", 365)
    raw_retention_days = _int("EVENT_RAW_RETENTION_DAYS", 90)
    audit_retention_days = _int("AUDIT_LOG_RETENTION_DAYS", 730)
    notification_retention_days = _int("NOTIFICATION_RETENTION_DAYS", 180)


config = WorkerConfig
