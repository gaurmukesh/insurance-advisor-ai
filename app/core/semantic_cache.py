import hashlib
import redis.asyncio as redis
from app.core.config import settings

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if not _redis:
        _redis = redis.from_url(getattr(settings, "REDIS_URL", "redis://localhost:6379"))
    return _redis


def _cache_key(system: str, user: str) -> str:
    return "llm:" + hashlib.sha256(f"{system}||{user}".encode()).hexdigest()


async def get_cached(system: str, user: str) -> str | None:
    try:
        val = await _get_redis().get(_cache_key(system, user))
        return val.decode() if val else None
    except Exception:
        return None


async def set_cached(system: str, user: str, value: str, ttl: int = 3600) -> None:
    try:
        await _get_redis().setex(_cache_key(system, user), ttl, value)
    except Exception:
        pass
