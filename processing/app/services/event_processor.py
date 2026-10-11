import json
from datetime import datetime, timezone

from app.clients.kafka_client import commit, get_consumer, publish
from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import DeadLetterRecord
from app.services.validator import (
    EventValidationError,
    build_clean_event,
    parse_raw_event,
)

logger = get_logger(__name__)


async def send_to_dlq(message, error: EventValidationError) -> None:
    """Writes a failed message to dlq_events with enough context to trace
    it back to its exact position in raw_events."""
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
    logger.warning(
        "event_sent_to_dlq",
        error_type=error.error_type,
        partition=message.partition,
        offset=message.offset,
    )


async def process_message(message) -> None:
    """Parses, validates and routes one Kafka message. Every message ends up
    on exactly one of clean_events or dlq_events."""
    try:
        raw_event = parse_raw_event(message.value)
    except EventValidationError as err:
        await send_to_dlq(message, err)
        return

    clean_event = build_clean_event(raw_event, settings.known_property_key_set)

    # Phase 3 hook: when clean_event.unknown_keys is non-empty, call the
    # Intelligence service over gRPC here before publishing.
    if clean_event.unknown_keys:
        logger.info(
            "unknown_keys_detected",
            event_id=clean_event.event_id,
            unknown_keys=clean_event.unknown_keys,
        )

    await publish(
        settings.kafka_clean_events_topic,
        key=message.key,
        value=clean_event.model_dump_json().encode("utf-8"),
    )
    logger.info("event_processed", event_id=clean_event.event_id)


async def run_consumer() -> None:
    """Main loop. The offset is committed only after a message has been
    routed, so a crash re-delivers it instead of losing it."""
    consumer = get_consumer()
    async for message in consumer:
        try:
            await process_message(message)
        except Exception:
            # Unexpected failure (for example the broker rejecting a publish).
            # Do not commit: the message will be re-delivered on restart.
            logger.exception(
                "unexpected_processing_error",
                partition=message.partition,
                offset=message.offset,
            )
            raise
        await commit()