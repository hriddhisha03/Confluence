import asyncio
from collections.abc import Awaitable, Callable

from app.clients.postgres_client import load_known_keys
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class KnownKeysCache:
    """
    In-memory copy of the schema registry's field names. The hot path reads
    this set, so Postgres is queried once per refresh interval and never
    once per event.

    Failure behaviour: if a refresh fails, or the registry comes back empty,
    the previous keys stay in use. A Postgres blip degrades freshness; it
    does not stop event processing.
    """

    def __init__(
        self,
        loader: Callable[[], Awaitable[set[str]]],
        fallback: set[str],
        refresh_seconds: float,
    ):
        self._loader = loader
        self._keys: set[str] = set(fallback)
        self._refresh_seconds = refresh_seconds

    def get(self) -> set[str]:
        return set(self._keys)

    async def refresh(self) -> None:
        try:
            keys = await self._loader()
        except Exception:
            logger.warning("known_keys_refresh_failed", keeping=len(self._keys), exc_info=True)
            return
        if not keys:
            logger.warning("known_keys_registry_empty", keeping=len(self._keys))
            return
        added = keys - self._keys
        if added:
            logger.info("known_keys_updated", added=sorted(added), total=len(keys))
        self._keys = keys

    async def run_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_seconds)
            await self.refresh()


known_keys_cache = KnownKeysCache(
    loader=load_known_keys,
    fallback=settings.known_property_key_set,
    refresh_seconds=settings.known_keys_refresh_seconds,
)