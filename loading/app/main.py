import asyncio
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.loader import run_loader

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main():
    logger.info("starting_loading_service")
    await run_loader()


if __name__ == "__main__":
    asyncio.run(main())
