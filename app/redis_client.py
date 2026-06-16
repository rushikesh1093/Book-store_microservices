"""
app/redis_client.py

Async Redis connection shared across the service (pub/sub consumer + health
checks). A single client is created lazily and reused.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("analytics.redis")

_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    """Return a lazily-initialised shared async Redis client."""
    global _client
    if _client is None:
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
    """Ping Redis for the /health probe."""
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
