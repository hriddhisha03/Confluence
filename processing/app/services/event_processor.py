import json
from datetime import datetime, timezone

from app.clients.kafka_client import commit, get_consumer, publish
from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import DeadLetterRecord
from app.services.known_keys import known_keys_cache
from app.services.schema_resolver import schema_resolver
from app.services.validator import (
    EventValidationError,
    build_clean_event,
    parse_raw_event,
)

logger = get_logger(__name__)


async def send_to_dlq(message, error: EventValidationError) -> None:
    record = DeadLetterRecord(
        original_payload=message.value.decode("utf-8", errors="replace"),
        error_type=error.error_type,
        error_detail=error.detail,
        source_topic=message.topic,
        source_partition=message.partition,
        source_offset=message.offset,
        failed_at=datetime.now(timezone.utc),
    )
    await publish(
        settings.kafka_dlq_topic,
        key=message.key,
        value=record.model_dump_json().encode("utf-8"),
    )
    logger.warning("event_sent_to_dlq", error_type=error.error_type, partition=message.partition, offset=message.offset)


async def process_message(message) -> None:
    try:
        raw_event = parse_raw_event(message.value)
    except EventValidationError as err:
        await send_to_dlq(message, err)
        return

    clean_event = build_clean_event(raw_event, known_keys_cache.get())

    if clean_event.unknown_keys:
        logger.info("unknown_keys_detected", event_id=clean_event.event_id, unknown_keys=clean_event.unknown_keys)

    await publish(
        settings.kafka_clean_events_topic,
        key=message.key,
        value=clean_event.model_dump_json().encode("utf-8"),
    )
    logger.info("event_processed", event_id=clean_event.event_id)

    # Resolved after publishing so a slow Intelligence call never delays the
    # event itself. resolve() never raises.
    if clean_event.unknown_keys:
        await schema_resolver.resolve(clean_event)


async def run_consumer() -> None:
    consumer = get_consumer()
    async for message in consumer:
        try:
            await process_message(message)
        except Exception:
            logger.exception("unexpected_processing_error", partition=message.partition, offset=message.offset)
            raise
        await commit()