import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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