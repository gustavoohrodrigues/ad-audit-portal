"""Configuração do Celery e agendamento (beat) das tarefas periódicas."""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

broker = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://redis:6379/1"))
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery("ad_audit_worker", broker=broker, backend=backend)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("APP_TIMEZONE", "America/Sao_Paulo"),
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
)

# tarefas registradas
celery_app.autodiscover_tasks(["app.tasks"])
from app.tasks import alerts, correlation, retention, risk  # noqa: E402,F401

_poll = int(os.getenv("EVENT_POLL_INTERVAL_SECONDS", "60"))

celery_app.conf.beat_schedule = {
    "correlate-events": {
        "task": "app.tasks.correlation.correlate_recent",
        "schedule": max(_poll, 60),
    },
    "recompute-risk": {
        "task": "app.tasks.risk.recompute_recent_risk",
        "schedule": max(_poll * 2, 120),
    },
    "evaluate-alerts": {
        "task": "app.tasks.alerts.evaluate_and_dispatch",
        "schedule": max(_poll, 60),
    },
    "apply-retention": {
        "task": "app.tasks.retention.apply_retention",
        "schedule": crontab(hour=3, minute=0),  # diariamente 03:00
    },
    "refresh-dc-health": {
        "task": "app.tasks.correlation.refresh_source_health",
        "schedule": 120,
    },
}
