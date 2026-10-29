from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from app.clients.intelligence_client import intelligence_client
from app.clients.kafka_client import publish
from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import CleanEvent, InferResult, SchemaUpdate
from app.services.known_keys import KnownKeysCache, known_keys_cache

logger = get_logger(__name__)


class SchemaResolver:
    """
    Turns unknown keys on an event into registered schema fields by asking
    Intelligence. It must never break event flow: every failure is logged and
    swallowed, and the event is published to clean_events regardless.
    """

    def __init__(
        self,
        infer: Callable[[dict[str, list[Any]]], Awaitable[InferResult | None]],
        publish_message: Callable[[str, bytes | None, bytes], Awaitable[None]],
        cache: KnownKeysCache,
        topic: str,
        max_rejected: int,
    ):
        self._infer = infer
        self._publish = publish_message
        self._cache = cache
        self._topic = topic
        self._max_rejected = max_rejected
        self._rejected: dict[str, None] = {}  # insertion-ordered, oldest evicted first

    def _remember_rejected(self, name: str) -> None:
        self._rejected[name] = None
        while len(self._rejected) > self._max_rejected:
            self._rejected.pop(next(iter(self._rejected)))

    async def resolve(self, event: CleanEvent) -> None:
        try:
            await self._resolve(event)
        except Exception:
            logger.exception("schema_resolution_failed", event_id=event.event_id)

    async def _resolve(self, event: CleanEvent) -> None:
        unknown = [k for k in event.unknown_keys if k not in self._rejected]
        if not unknown:
            return

        samples = {k: [event.properties.get(k)] for k in unknown}
        result = await self._infer(samples)
        if result is None:
            return  # Intelligence unavailable; the next event with these keys retries

        self._cache.add({f.name for f in result.registered} | {f.name for f in result.existing})
        for rejected in result.rejected:
            self._remember_rejected(rejected.name)

        if result.registered:
            update = SchemaUpdate(
                schema_version=result.schema_version,
                fields=result.registered,
                emitted_at=datetime.now(timezone.utc),
            )
            await self._publish(self._topic, None, update.model_dump_json().encode("utf-8"))
            logger.info(
                "schema_update_published",
                schema_version=result.schema_version,
                fields=[f.name for f in result.registered],
            )


schema_resolver = SchemaResolver(
    infer=intelligence_client.infer,
    publish_message=publish,
    cache=known_keys_cache,
    topic=settings.kafka_schema_updates_topic,
    max_rejected=settings.rejected_keys_max,
)