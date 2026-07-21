"""Middlewares: headers de segurança, rate limiting e métricas."""
from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.metrics import http_request_duration, http_requests_total
from app.core.redis_client import redis_client

settings = get_settings()

# Cabeçalhos de segurança. Como o TLS é terminado no NPM, HSTS pode ser
# adicionado aqui ou no NPM (recomendado no NPM). Mantemos os essenciais.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if settings.tls_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        http_requests_total.labels(
            method=request.method, path=path, status=response.status_code
        ).inc()
        http_request_duration.labels(method=request.method, path=path).observe(elapsed)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit simples por IP via Redis (janela fixa por minuto)."""

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled or request.url.path.endswith(
            ("/health", "/readiness", "/metrics")
        ):
            return await call_next(request)

        is_login = request.url.path.endswith("/auth/login")
        limit = _parse_limit(
            settings.rate_limit_login if is_login else settings.rate_limit_default
        )
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        window = int(time.time() // 60)
        key = f"rl:{'login' if is_login else 'def'}:{ip}:{window}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, 60)
            if count > limit:
                return Response(
                    content='{"detail":"Rate limit excedido"}',
                    status_code=429,
                    media_type="application/json",
                )
        except Exception:  # Redis indisponível: não bloqueia a aplicação
            pass
        return await call_next(request)


def _parse_limit(spec: str) -> int:
    try:
        return int(spec.split("/")[0])
    except (ValueError, IndexError):
        return 120
