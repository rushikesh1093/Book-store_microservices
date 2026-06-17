"""
app/redis_client.py

Optional async Redis client used only when the event consumer is explicitly
enabled (REDIS_CONSUMER_ENABLED=True with a reachable REDIS_URL). The service
runs fully without Redis, so the ``redis`` package is imported lazily and is
not a hard dependency.
"""
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger("analytics.redis")

_client = None  # type: ignore[var-annotated]


def get_redis():
    """Return a lazily-initialised shared async Redis client.

    Imports ``redis`` on first use so the package is only required when Redis
    is actually enabled.
    """
    global _client
    if _client is None:
        import redis.asyncio as aioredis  # lazy import

        _client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _client


async def check_redis() -> bool:
    """Ping Redis (used only if Redis is enabled)."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Redis health check failed: %s", exc)
        return False


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
