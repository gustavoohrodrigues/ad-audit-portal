"""Métricas Prometheus da aplicação."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "adaudit_http_requests_total",
    "Total de requisições HTTP",
    ["method", "path", "status"],
)
http_request_duration = Histogram(
    "adaudit_http_request_duration_seconds",
    "Duração das requisições HTTP",
    ["method", "path"],
)
login_attempts_total = Counter(
    "adaudit_login_attempts_total", "Tentativas de login", ["result"]
)
events_query_total = Counter(
    "adaudit_events_query_total", "Consultas a eventos", ["kind"]
)
raw_event_access_total = Counter(
    "adaudit_raw_event_access_total", "Acessos a JSON bruto de evento"
)
alerts_active = Gauge(
    "adaudit_alerts_active", "Alertas ativos por severidade", ["severity"]
)
source_up = Gauge(
    "adaudit_source_up", "Status da fonte de eventos (1=up,0=down)", ["source"]
)
ingestion_lag_seconds = Gauge(
    "adaudit_ingestion_lag_seconds", "Atraso de ingestão por DC", ["dc"]
)
