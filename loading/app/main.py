import asyncio

from app.clients.clickhouse_client import start_clickhouse, stop_clickhouse
from app.clients.kafka_client import start_kafka, stop_kafka
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.loader import run_loader

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main() -> None:
    logger.info("starting_loading_service")
    await start_clickhouse()
    try:
        await start_kafka()
        await run_loader()
    finally:
        await stop_kafka()
        await stop_clickhouse()


if __name__ == "__main__":
    asyncio.run(main())