"""Cache Redis com TTL, proteção contra stampede e métricas hit/miss.

Namespaces por tipo; prefixo por ambiente. Nunca cacheia PII sensível sem
considerar RBAC (o chamador decide a chave por perfil quando necessário).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter

from app.config import get_settings
from app.core.logging import get_logger
from app.core.redis_client import redis_client

settings = get_settings()
logger = get_logger(__name__)

cache_hits = Counter("adaudit_cache_hits_total", "Cache hits", ["namespace"])
cache_misses = Counter("adaudit_cache_misses_total", "Cache misses", ["namespace"])

_PREFIX = f"cache:{settings.app_env}:"


def _key(namespace: str, key: str) -> str:
    return f"{_PREFIX}{namespace}:{key}"


async def get_or_set(
    namespace: str,
    key: str,
    ttl: int,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    """Retorna do cache ou executa ``loader`` e cacheia. Protege contra stampede
    com lock curto; se não conseguir o lock, aguarda e relê antes de recorrer ao
    loader. Falhas de Redis fazem fallback direto ao loader (nunca quebram a API).
    """
    if not settings.cache_enabled:
        return await loader()

    rkey = _key(namespace, key)
    try:
        cached = await redis_client.get(rkey)
    except Exception:  # noqa: BLE001
        return await loader()

    if cached is not None:
        cache_hits.labels(namespace=namespace).inc()
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    cache_misses.labels(namespace=namespace).inc()

    lock_key = f"{rkey}:lock"
    got_lock = False
    try:
        got_lock = bool(
            await redis_client.set(lock_key, "1", nx=True, ex=settings.cache_stampede_lock_seconds)
        )
    except Exception:  # noqa: BLE001
        got_lock = True

    if not got_lock:
        # outra requisição está computando; espera breve e relê
        for _ in range(20):
            await asyncio.sleep(0.05)
            try:
                cached = await redis_client.get(rkey)
            except Exception:  # noqa: BLE001
                break
            if cached is not None:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    break

    value = await loader()
    try:
        await redis_client.setex(rkey, ttl, json.dumps(value, default=str))
    except Exception:  # noqa: BLE001
        pass
    finally:
        if got_lock:
            try:
                await redis_client.delete(lock_key)
            except Exception:  # noqa: BLE001
                pass
    return value


async def invalidate(namespace: str) -> int:
    """Invalida todas as chaves de um namespace (usar após sync/mudança)."""
    try:
        pattern = _key(namespace, "*")
        deleted = 0
        async for k in redis_client.scan_iter(match=pattern, count=200):
            await redis_client.delete(k)
            deleted += 1
        return deleted
    except Exception:  # noqa: BLE001
        return 0
