import asyncio

import clickhouse_connect

from app.core.config import settings
from app.core.logging import get_logger
from app.services.transform import COLUMNS

logger = get_logger(__name__)

_client = None


async def start_clickhouse() -> None:
    global _client
    # clickhouse-connect is synchronous, so calls run in a worker thread to
    # keep the event loop (and the Kafka consumer heartbeat) responsive.
    _client = await asyncio.to_thread(
        clickhouse_connect.get_client,
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )
    logger.info("clickhouse_started", host=settings.clickhouse_host)


async def stop_clickhouse() -> None:
    global _client
    if _client is not None:
        await asyncio.to_thread(_client.close)
        _client = None
        logger.info("clickhouse_stopped")


async def insert_rows(rows: list[list]) -> None:
    if _client is None:
        raise RuntimeError("ClickHouse client not started")
    await asyncio.to_thread(
        _client.insert,
        settings.clickhouse_table,
        rows,
        column_names=list(COLUMNS),
    )
