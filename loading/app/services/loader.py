import asyncio
from datetime import datetime, timezone

from app.clients.clickhouse_client import insert_rows
from app.clients.kafka_client import commit, get_consumer, publish
from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import DeadLetterRecord
from app.services.transform import EventParseError, parse_clean_event, to_row

logger = get_logger(__name__)


async def collect_batch(consumer, batch_size: int, interval_seconds: float) -> list:
    """Gathers messages until batch_size is reached or interval_seconds have
    passed, whichever comes first. Bounds both memory and latency."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + interval_seconds
    collected: list = []
    while len(collected) < batch_size:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        batches = await consumer.getmany(
            timeout_ms=int(remaining * 1000),
            max_records=batch_size - len(collected),
        )
        for messages in batches.values():
            collected.extend(messages)
    return collected


async def send_to_dlq(message, error: EventParseError) -> None:
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


async def insert_with_retry(
    rows: list[list],
    max_retries: int | None = None,
    backoff_seconds: float | None = None,
) -> None:
    """Inserts one batch, retrying with exponential backoff. After the last
    retry the error is raised and the offset is NOT committed, so the batch
    is re-delivered after a restart instead of being lost."""
    retries = settings.insert_max_retries if max_retries is None else max_retries
    backoff = settings.insert_retry_backoff_seconds if backoff_seconds is None else backoff_seconds

    for attempt in range(retries + 1):
        try:
            await insert_rows(rows)
            return
        except Exception:
            if attempt == retries:
                logger.exception("clickhouse_insert_failed_giving_up", rows=len(rows))
                raise
            delay = backoff * (2 ** attempt)
            logger.warning("clickhouse_insert_failed_retrying", attempt=attempt + 1, delay=delay, exc_info=True)
            await asyncio.sleep(delay)


async def process_batch(messages: list) -> int:
    """Parses a batch, dead-letters the unparseable messages, and inserts the
    rest in a single ClickHouse insert. Returns the number of rows inserted."""
    rows: list[list] = []
    for message in messages:
        try:
            rows.append(to_row(parse_clean_event(message.value)))
        except EventParseError as err:
            await send_to_dlq(message, err)

    if rows:
        await insert_with_retry(rows)
        logger.info("batch_loaded", rows=len(rows), consumed=len(messages))
    return len(rows)


async def run_loader() -> None:
    consumer = get_consumer()
    while True:
        messages = await collect_batch(consumer, settings.batch_size, settings.batch_interval_seconds)
        if not messages:
            continue
        await process_batch(messages)
        await commit()