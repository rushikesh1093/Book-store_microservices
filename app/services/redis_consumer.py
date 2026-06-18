"""
app/services/redis_consumer.py

Subscribes to the platform's Redis pub/sub channels and persists each event to
the ``analytics_events`` table for later aggregation.

Channels:
  * order_created
  * book_viewed
  * search_query
  * recommendation_clicked

Event payloads are expected to be JSON. We extract a few common fields
(user_id, book_id) when present and store the full payload as text.
"""
import asyncio
import json
import logging
from typing import Optional

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.events import AnalyticsEvent
from app.redis_client import get_redis

logger = logging.getLogger("analytics.consumer")


class RedisEventConsumer:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="redis-event-consumer")
        logger.info("Redis event consumer started for channels: %s",
                    ", ".join(settings.EVENT_CHANNELS))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Redis event consumer stopped.")

    async def _run(self) -> None:
        backoff = 1
        while self._running:
            try:
                redis = get_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(*settings.EVENT_CHANNELS)
                backoff = 1  # reset after a successful subscribe
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message.get("type") != "message":
                        continue
                    await self._handle(message["channel"], message["data"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - resilience path
                logger.warning("Consumer error (%s); reconnecting in %ss", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _handle(self, channel: str, data: str) -> None:
        payload = self._parse(data)
        event = AnalyticsEvent(
            event_type=channel,
            user_id=_str_or_none(payload.get("user_id")),
            book_id=_str_or_none(payload.get("book_id")),
            payload=json.dumps(payload) if payload else (data or None),
        )
        try:
            async with AsyncSessionLocal() as session:
                session.add(event)
                await session.commit()
        except Exception:  # pragma: no cover - never crash the loop
            logger.exception("Failed to persist event from channel %s", channel)

    @staticmethod
    def _parse(data: str) -> dict:
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (ValueError, TypeError):
            return {"raw": data}


def _str_or_none(value) -> Optional[str]:
    return str(value) if value not in (None, "") else None


# Module-level singleton used by the app lifespan.
consumer = RedisEventConsumer()
