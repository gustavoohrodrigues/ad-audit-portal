"""Cliente Redis compartilhado — cache, revogação de refresh token, rate limit."""
from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

redis_client: redis.Redis = redis.from_url(
    settings.redis_url, encoding="utf-8", decode_responses=True
)

REFRESH_PREFIX = "refresh:"


async def store_refresh_jti(jti: str, subject: str) -> None:
    ttl = settings.jwt_refresh_token_expire_days * 86400
    await redis_client.setex(f"{REFRESH_PREFIX}{jti}", ttl, subject)


async def is_refresh_valid(jti: str, subject: str) -> bool:
    val = await redis_client.get(f"{REFRESH_PREFIX}{jti}")
    return val == subject


async def revoke_refresh(jti: str) -> None:
    await redis_client.delete(f"{REFRESH_PREFIX}{jti}")


async def ping() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False
