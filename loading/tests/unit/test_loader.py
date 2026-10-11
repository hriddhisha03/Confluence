import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import loader

VALID = {
    "event_id": "evt-1",
    "event_type": "page_view",
    "user_id": "user-1",
    "session_id": "session-1",
    "url": "https://example.com",
    "timestamp": "2026-10-11T10:00:00Z",
    "properties": {"browser": "chrome"},
    "unknown_keys": [],
    "processed_at": "2026-10-11T10:00:01Z",
}


def msg(value: bytes, offset: int = 0):
    return SimpleNamespace(value=value, key=b"s", topic="clean_events", partition=0, offset=offset)


def good(offset: int = 0):
    return msg(json.dumps({**VALID, "event_id": f"evt-{offset}"}).encode(), offset)


class FakeConsumer:
    """Returns scripted getmany() responses, then waits out the timeout."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def getmany(self, timeout_ms, max_records):
        self.calls.append((timeout_ms, max_records))
        if self.responses:
            return self.responses.pop(0)
        await asyncio.sleep(timeout_ms / 1000)
        return {}


# ---- process_batch ----

async def test_valid_batch_is_one_insert():
    with patch.object(loader, "insert_rows", new_callable=AsyncMock) as ins, \
         patch.object(loader, "publish", new_callable=AsyncMock) as pub:
        inserted = await loader.process_batch([good(0), good(1), good(2)])

    assert inserted == 3
    ins.assert_awaited_once()
    assert len(ins.await_args.args[0]) == 3
    pub.assert_not_awaited()


async def test_bad_message_goes_to_dlq_and_good_ones_still_load():
    with patch.object(loader, "insert_rows", new_callable=AsyncMock) as ins, \
         patch.object(loader, "publish", new_callable=AsyncMock) as pub:
        inserted = await loader.process_batch([good(0), msg(b"{broken", 1), good(2)])

    assert inserted == 2
    assert len(ins.await_args.args[0]) == 2
    pub.assert_awaited_once()
    assert pub.await_args.args[0] == "dlq_events"
    record = json.loads(pub.await_args.kwargs["value"])
    assert record["error_type"] == "invalid_json"
    assert record["source_offset"] == 1


async def test_all_bad_batch_makes_no_insert():
    with patch.object(loader, "insert_rows", new_callable=AsyncMock) as ins, \
         patch.object(loader, "publish", new_callable=AsyncMock):
        inserted = await loader.process_batch([msg(b"x", 0), msg(b"y", 1)])

    assert inserted == 0
    ins.assert_not_awaited()


# ---- insert_with_retry ----

async def test_insert_retries_then_succeeds():
    mock = AsyncMock(side_effect=[ConnectionError("down"), ConnectionError("down"), None])
    with patch.object(loader, "insert_rows", mock):
        await loader.insert_with_retry([["r"]], max_retries=3, backoff_seconds=0)
    assert mock.await_count == 3


async def test_insert_raises_after_max_retries():
    mock = AsyncMock(side_effect=ConnectionError("down"))
    with patch.object(loader, "insert_rows", mock):
        with pytest.raises(ConnectionError):
            await loader.insert_with_retry([["r"]], max_retries=2, backoff_seconds=0)
    assert mock.await_count == 3  # first attempt + 2 retries


async def test_insert_no_retry_when_first_attempt_succeeds():
    mock = AsyncMock()
    with patch.object(loader, "insert_rows", mock):
        await loader.insert_with_retry([["r"]], max_retries=3, backoff_seconds=0)
    mock.assert_awaited_once()


# ---- collect_batch ----

async def test_collect_batch_stops_when_batch_size_reached():
    consumer = FakeConsumer([
        {"tp": [good(0), good(1)]},
        {"tp": [good(2)]},
    ])
    result = await loader.collect_batch(consumer, batch_size=3, interval_seconds=5)
    assert len(result) == 3
    # Second call only asks for what is still missing.
    assert consumer.calls[1][1] == 1


async def test_collect_batch_stops_at_deadline_with_partial_batch():
    consumer = FakeConsumer([{"tp": [good(0)]}])
    result = await loader.collect_batch(consumer, batch_size=100, interval_seconds=0.2)
    assert len(result) == 1


async def test_collect_batch_returns_empty_when_nothing_arrives():
    consumer = FakeConsumer([])
    result = await loader.collect_batch(consumer, batch_size=10, interval_seconds=0.1)
    assert result == []