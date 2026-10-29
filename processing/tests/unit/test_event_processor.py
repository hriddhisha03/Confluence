import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import event_processor

VALID = {
    "event_id": "evt-1",
    "event_type": "page_view",
    "user_id": "user-1",
    "session_id": "session-1",
    "url": "https://example.com/pricing",
    "timestamp": "2026-10-04T10:00:00Z",
    "properties": {"browser": "chrome", "campaign": "fall"},
}

@pytest.fixture(autouse=True)
def resolver_mock():
    with patch.object(event_processor.schema_resolver, "resolve", new_callable=AsyncMock) as m:
        yield m

def make_message(value: bytes, key: bytes = b"session-1"):
    return SimpleNamespace(
        value=value, key=key, topic="raw_events", partition=2, offset=17
    )


async def test_valid_message_goes_to_clean_events():
    with patch.object(event_processor, "publish", new_callable=AsyncMock) as pub:
        await event_processor.process_message(make_message(json.dumps(VALID).encode()))

    pub.assert_awaited_once()
    topic = pub.await_args.args[0]
    body = json.loads(pub.await_args.kwargs["value"])
    assert topic == "clean_events"
    assert body["event_id"] == "evt-1"
    assert body["unknown_keys"] == ["campaign"]
    assert pub.await_args.kwargs["key"] == b"session-1"


async def test_malformed_message_goes_to_dlq_with_context():
    with patch.object(event_processor, "publish", new_callable=AsyncMock) as pub:
        await event_processor.process_message(make_message(b"{broken"))

    pub.assert_awaited_once()
    assert pub.await_args.args[0] == "dlq_events"
    record = json.loads(pub.await_args.kwargs["value"])
    assert record["error_type"] == "invalid_json"
    assert record["original_payload"] == "{broken"
    assert record["source_topic"] == "raw_events"
    assert record["source_partition"] == 2
    assert record["source_offset"] == 17


async def test_message_never_goes_to_both_topics():
    with patch.object(event_processor, "publish", new_callable=AsyncMock) as pub:
        await event_processor.process_message(make_message(json.dumps(VALID).encode()))
        await event_processor.process_message(make_message(b"nope"))

    topics = [c.args[0] for c in pub.await_args_list]
    assert topics == ["clean_events", "dlq_events"]

async def test_resolver_called_for_event_with_unknown_keys(resolver_mock):
    with patch.object(event_processor, "publish", new_callable=AsyncMock):
        await event_processor.process_message(make_message(json.dumps(VALID).encode()))
    resolver_mock.assert_awaited_once()
    assert resolver_mock.await_args.args[0].unknown_keys == ["campaign"]


async def test_resolver_not_called_when_all_keys_known(resolver_mock):
    known = dict(VALID, properties={"browser": "chrome"})
    with patch.object(event_processor, "publish", new_callable=AsyncMock):
        await event_processor.process_message(make_message(json.dumps(known).encode()))
    resolver_mock.assert_not_awaited()


async def test_resolver_runs_after_clean_publish(resolver_mock):
    order = []
    pub = AsyncMock(side_effect=lambda *a, **k: order.append("publish"))
    resolver_mock.side_effect = lambda *a, **k: order.append("resolve")
    with patch.object(event_processor, "publish", pub):
        await event_processor.process_message(make_message(json.dumps(VALID).encode()))
    assert order == ["publish", "resolve"]


async def test_resolver_not_called_for_dlq(resolver_mock):
    with patch.object(event_processor, "publish", new_callable=AsyncMock):
        await event_processor.process_message(make_message(b"{broken"))
    resolver_mock.assert_not_awaited()