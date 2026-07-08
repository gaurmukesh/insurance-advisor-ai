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


def _prefixed_key(prefix: str, key: str) -> str:
    return f"{prefix}:" + hashlib.sha256(key.encode()).hexdigest()


async def get_cached_value(prefix: str, key: str) -> str | None:
    """General-purpose Redis cache lookup, keyed by an arbitrary string (e.g. an
    embedding model + input text) rather than the fixed system/user prompt shape."""
    try:
        val = await _get_redis().get(_prefixed_key(prefix, key))
        return val.decode() if val else None
    except Exception:
        return None


async def set_cached_value(prefix: str, key: str, value: str, ttl: int = 86400) -> None:
    try:
        await _get_redis().setex(_prefixed_key(prefix, key), ttl, value)
    except Exception:
        pass
