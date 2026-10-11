import asyncio

from app.clients.kafka_client import start_kafka, stop_kafka
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.event_processor import run_consumer

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main() -> None:
    logger.info("starting_processing_service")
    await start_kafka()
    try:
        await run_consumer()
    finally:
        await stop_kafka()


if __name__ == "__main__":
    asyncio.run(main())