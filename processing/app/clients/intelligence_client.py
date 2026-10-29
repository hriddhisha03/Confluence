import time
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import InferResult

logger = get_logger(__name__)


class IntelligenceClient:
    """
    HTTP client for the Intelligence service. infer() never raises for network
    or HTTP errors: it returns None and opens a cooldown window during which
    no further calls are made. Event processing must keep flowing when
    Intelligence is slow or down.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        client: httpx.AsyncClient | None = None,
    ):
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._client = client
        self._blocked_until = 0.0

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        logger.info("intelligence_client_started", url=self._base_url)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def infer(self, samples: dict[str, list[Any]]) -> InferResult | None:
        if self._client is None:
            raise RuntimeError("Intelligence client not started")

        now = self._clock()
        if now < self._blocked_until:
            return None

        try:
            response = await self._client.post("/v1/infer", json={"samples": samples})
            response.raise_for_status()
            return InferResult.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            self._blocked_until = now + self._cooldown
            logger.warning(
                "intelligence_call_failed",
                error=type(exc).__name__,
                cooldown_seconds=self._cooldown,
            )
            return None


intelligence_client = IntelligenceClient(
    base_url=settings.intelligence_url,
    timeout_seconds=settings.intelligence_timeout_seconds,
    cooldown_seconds=settings.intelligence_cooldown_seconds,
)