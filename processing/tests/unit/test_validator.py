import json
from datetime import datetime, timezone

import pytest

from app.models.schemas import RawEvent
from app.services.validator import (
    EventValidationError,
    build_clean_event,
    find_unknown_keys,
    normalize_properties,
    parse_raw_event,
)

VALID = {
    "event_id": "evt-1",
    "event_type": "page_view",
    "user_id": "user-1",
    "session_id": "session-1",
    "url": "https://example.com/pricing",
    "timestamp": "2026-10-04T10:00:00Z",
    "properties": {"browser": "chrome", "referrer": "google"},
}

FIXED_NOW = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)


def encode(obj) -> bytes:
    return json.dumps(obj).encode("utf-8")


# ---- parse_raw_event ----

def test_parse_valid_event():
    event = parse_raw_event(encode(VALID))
    assert event.event_id == "evt-1"
    assert event.properties == {"browser": "chrome", "referrer": "google"}


def test_parse_invalid_encoding():
    with pytest.raises(EventValidationError) as exc:
        parse_raw_event(b"\xff\xfe\xfa")
    assert exc.value.error_type == "invalid_encoding"


def test_parse_invalid_json():
    with pytest.raises(EventValidationError) as exc:
        parse_raw_event(b"{not json")
    assert exc.value.error_type == "invalid_json"


@pytest.mark.parametrize("payload", [b"[1, 2, 3]", b'"just a string"', b"42", b"null"])
def test_parse_non_object_json(payload):
    with pytest.raises(EventValidationError) as exc:
        parse_raw_event(payload)
    assert exc.value.error_type == "invalid_structure"


def test_parse_missing_required_field():
    bad = {k: v for k, v in VALID.items() if k != "user_id"}
    with pytest.raises(EventValidationError) as exc:
        parse_raw_event(encode(bad))
    assert exc.value.error_type == "schema_violation"
    assert "user_id" in exc.value.detail


def test_parse_bad_timestamp():
    bad = {**VALID, "timestamp": "not-a-date"}
    with pytest.raises(EventValidationError) as exc:
        parse_raw_event(encode(bad))
    assert exc.value.error_type == "schema_violation"
    assert "timestamp" in exc.value.detail


# ---- normalize_properties ----

def test_normalize_properties_lowercases_and_strips():
    result = normalize_properties({"Browser": "chrome", " Referrer ": "google"})
    assert result == {"browser": "chrome", "referrer": "google"}


def test_normalize_properties_drops_empty_keys():
    assert normalize_properties({"": 1, "   ": 2, "ok": 3}) == {"ok": 3}


def test_normalize_properties_collapses_case_variants():
    result = normalize_properties({"Browser": "a", "browser": "b"})
    assert list(result) == ["browser"]


# ---- find_unknown_keys ----

def test_find_unknown_keys_none():
    assert find_unknown_keys({"browser": "x"}, {"browser", "referrer"}) == []


def test_find_unknown_keys_sorted():
    result = find_unknown_keys({"zeta": 1, "alpha": 2, "browser": 3}, {"browser"})
    assert result == ["alpha", "zeta"]


# ---- build_clean_event ----

def test_build_clean_event_known_keys_only():
    raw = RawEvent.model_validate(VALID)
    clean = build_clean_event(raw, {"browser", "referrer"}, now=FIXED_NOW)
    assert clean.unknown_keys == []
    assert clean.processed_at == FIXED_NOW


def test_build_clean_event_flags_unknown_keys():
    raw = RawEvent.model_validate({**VALID, "properties": {"browser": "x", "Campaign": "fall"}})
    clean = build_clean_event(raw, {"browser", "referrer"}, now=FIXED_NOW)
    assert clean.unknown_keys == ["campaign"]
    assert "campaign" in clean.properties


def test_build_clean_event_normalizes_event_type():
    raw = RawEvent.model_validate({**VALID, "event_type": "  Page_View "})
    clean = build_clean_event(raw, set(), now=FIXED_NOW)
    assert clean.event_type == "page_view"


def test_build_clean_event_assumes_utc_for_naive_timestamp():
    raw = RawEvent.model_validate({**VALID, "timestamp": "2026-10-04T10:00:00"})
    clean = build_clean_event(raw, set(), now=FIXED_NOW)
    assert clean.timestamp.tzinfo is not None
    assert clean.timestamp.utcoffset().total_seconds() == 0