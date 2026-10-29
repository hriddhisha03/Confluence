import asyncio
import contextlib

from app.clients.intelligence_client import intelligence_client
from app.clients.kafka_client import start_kafka, stop_kafka
from app.clients.postgres_client import start_postgres, stop_postgres
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.event_processor import run_consumer
from app.services.known_keys import known_keys_cache

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main() -> None:
    logger.info("starting_processing_service")
    await start_postgres()
    await intelligence_client.start()
    refresh_task: asyncio.Task | None = None
    try:
        await start_kafka()
        await known_keys_cache.refresh()
        refresh_task = asyncio.create_task(known_keys_cache.run_refresh_loop())
        await run_consumer()
    finally:
        if refresh_task is not None:
            refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await refresh_task
        await stop_kafka()
        await intelligence_client.stop()
        await stop_postgres()


if __name__ == "__main__":
    asyncio.run(main())