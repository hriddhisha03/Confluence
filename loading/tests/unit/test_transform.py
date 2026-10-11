import json

import pytest

from app.services.transform import COLUMNS, EventParseError, parse_clean_event, to_row

VALID = {
    "event_id": "evt-1",
    "event_type": "page_view",
    "user_id": "user-1",
    "session_id": "session-1",
    "url": "https://example.com/pricing",
    "timestamp": "2026-10-11T10:00:00Z",
    "properties": {"referrer": "google", "browser": "chrome"},
    "unknown_keys": [],
    "processed_at": "2026-10-11T10:00:01Z",
}


def encode(obj) -> bytes:
    return json.dumps(obj).encode("utf-8")


def test_parse_valid_event():
    event = parse_clean_event(encode(VALID))
    assert event.event_id == "evt-1"
    assert event.properties["browser"] == "chrome"


def test_parse_invalid_encoding():
    with pytest.raises(EventParseError) as exc:
        parse_clean_event(b"\xff\xfe")
    assert exc.value.error_type == "invalid_encoding"


def test_parse_invalid_json():
    with pytest.raises(EventParseError) as exc:
        parse_clean_event(b"{nope")
    assert exc.value.error_type == "invalid_json"


def test_parse_missing_field_is_schema_violation():
    bad = {k: v for k, v in VALID.items() if k != "event_id"}
    with pytest.raises(EventParseError) as exc:
        parse_clean_event(encode(bad))
    assert exc.value.error_type == "schema_violation"
    assert "event_id" in exc.value.detail


def test_non_object_json_is_schema_violation():
    with pytest.raises(EventParseError) as exc:
        parse_clean_event(b"[1, 2]")
    assert exc.value.error_type == "schema_violation"


def test_to_row_matches_column_order():
    row = to_row(parse_clean_event(encode(VALID)))
    assert len(row) == len(COLUMNS)
    by_name = dict(zip(COLUMNS, row))
    assert by_name["event_id"] == "evt-1"
    assert by_name["url"] == "https://example.com/pricing"
    assert by_name["timestamp"].year == 2026


def test_to_row_serializes_properties_deterministically():
    row = to_row(parse_clean_event(encode(VALID)))
    payload = dict(zip(COLUMNS, row))["raw_payload"]
    assert payload == '{"browser":"chrome","referrer":"google"}'


def test_received_at_is_not_in_columns():
    assert "received_at" not in COLUMNS