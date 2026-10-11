import asyncpg

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def start_postgres() -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn=settings.postgres_dsn, min_size=1, max_size=3)
    logger.info("postgres_started")


async def stop_postgres() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("postgres_stopped")


async def load_known_keys() -> set[str]:
    """Reads every field name registered in the schema registry. The registry
    is append-only, so a field that was ever registered is a known key."""
    if _pool is None:
        raise RuntimeError("Postgres pool not started")
    rows = await _pool.fetch("SELECT DISTINCT field_name FROM schema_registry")
    return {row["field_name"].strip().lower() for row in rows}