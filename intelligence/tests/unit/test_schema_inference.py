import pytest

from app.services.schema_inference import (
    BOOL, DATETIME, FLOAT, INT, STRING,
    infer_field_type, infer_type, merge_types, validate_field_name,
)


@pytest.mark.parametrize("value,expected", [
    (True, BOOL),
    (False, BOOL),
    (7, INT),
    (3.14, FLOAT),
    ("hello", STRING),
    ("2026-10-11T10:00:00Z", DATETIME),
    ("2026-10-11 10:00:00", DATETIME),
    ("2026-10-11", STRING),          # a bare date is not treated as a datetime
    ("2026-13-99T99:99", STRING),    # looks like a datetime but is not valid
    ("12345", STRING),               # numeric-looking strings stay strings
    ([1, 2], STRING),
    ({"a": 1}, STRING),
])
def test_infer_type(value, expected):
    assert infer_type(value) == expected


def test_null_carries_no_type_information():
    assert infer_type(None) is None


def test_bool_is_not_confused_with_int():
    assert infer_type(True) == BOOL
    assert infer_field_type([True, 1]) == STRING


@pytest.mark.parametrize("a,b,expected", [
    (INT, INT, INT),
    (INT, FLOAT, FLOAT),
    (FLOAT, INT, FLOAT),
    (INT, STRING, STRING),
    (BOOL, INT, STRING),
    (DATETIME, STRING, STRING),
])
def test_merge_types(a, b, expected):
    assert merge_types(a, b) == expected


def test_field_type_widens_across_samples():
    assert infer_field_type([1, 2, 3.5]) == FLOAT


def test_field_type_ignores_nulls():
    assert infer_field_type([None, 4, None]) == INT


def test_field_type_defaults_to_string_when_all_null_or_empty():
    assert infer_field_type([None, None]) == STRING
    assert infer_field_type([]) == STRING


@pytest.mark.parametrize("name", ["plan", "utm_source", "a1", "x" * 63])
def test_valid_names(name):
    assert validate_field_name(name) is None


@pytest.mark.parametrize("name", [
    "Plan",                        # uppercase
    "1abc",                        # leading digit
    "_hidden",                     # leading underscore
    "has space",
    "has-dash",
    "drop table; --",
    "x`; DROP TABLE click_events; --",
    "",
    "x" * 64,                      # too long
])
def test_invalid_names(name):
    assert validate_field_name(name) == "invalid_name"


@pytest.mark.parametrize("name", ["event_id", "timestamp", "raw_payload", "received_at", "url"])
def test_reserved_names(name):
    assert validate_field_name(name) == "reserved_name"