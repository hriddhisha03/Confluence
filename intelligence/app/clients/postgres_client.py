import asyncpg

from app.core.config import settings
from app.core.logging import get_logger
from app.services.registry_service import RegisterResult

logger = get_logger(__name__)

# Serializes registry writes across all replicas of this service.
_REGISTRY_LOCK_ID = 727001

_pool: asyncpg.Pool | None = None


async def start_postgres() -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn=settings.postgres_dsn, min_size=1, max_size=5)
    logger.info("postgres_started")


async def stop_postgres() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("postgres_stopped")


class PgRegistryRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def get_registry(self) -> dict[str, str]:
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT ON (field_name) field_name, field_type
            FROM schema_registry
            ORDER BY field_name, schema_version DESC
            """
        )
        return {r["field_name"]: r["field_type"] for r in rows}

    async def current_version(self) -> int:
        return await self._pool.fetchval("SELECT COALESCE(MAX(version), 0) FROM schema_versions")

    async def register_fields(self, fields: dict[str, str], description: str) -> RegisterResult:
        """Appends a new schema version containing the given fields. Runs under
        an advisory lock and re-checks existence inside it, so two replicas
        registering the same new key cannot create duplicates."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock($1)", _REGISTRY_LOCK_ID)

                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (field_name) field_name, field_type
                    FROM schema_registry
                    WHERE field_name = ANY($1::text[])
                    ORDER BY field_name, schema_version DESC
                    """,
                    list(fields),
                )
                existing = {r["field_name"]: r["field_type"] for r in rows}
                to_insert = {n: t for n, t in fields.items() if n not in existing}

                if not to_insert:
                    version = await conn.fetchval("SELECT COALESCE(MAX(version), 0) FROM schema_versions")
                    return RegisterResult(version=version, existing=existing)

                version = await conn.fetchval("SELECT COALESCE(MAX(version), 0) + 1 FROM schema_versions")
                await conn.execute(
                    "INSERT INTO schema_versions (version, description) VALUES ($1, $2)",
                    version,
                    description,
                )
                await conn.executemany(
                    "INSERT INTO schema_registry (field_name, field_type, schema_version) VALUES ($1, $2, $3)",
                    [(n, t, version) for n, t in to_insert.items()],
                )
                logger.info("schema_version_registered", version=version, fields=sorted(to_insert))
                return RegisterResult(version=version, inserted=to_insert, existing=existing)


def get_repository() -> PgRegistryRepository:
    if _pool is None:
        raise RuntimeError("Postgres pool not started")
    return PgRegistryRepository(_pool)
