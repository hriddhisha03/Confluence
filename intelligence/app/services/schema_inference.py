import re
from datetime import datetime
from typing import Any

# Logical types. Loading maps these to ClickHouse types when it alters the table.
STRING = "string"
INT = "int"
FLOAT = "float"
BOOL = "bool"
DATETIME = "datetime"

# Names that already exist as columns in click_events.
RESERVED_NAMES = frozenset(
    {"event_id", "event_type", "user_id", "session_id", "url",
     "timestamp", "received_at", "raw_payload"}
)

# Field names become ClickHouse column names inside DDL, and they come from
# untrusted event data. Only this strict shape is ever allowed through.
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_DATETIME_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def infer_type(value: Any) -> str | None:
    """Returns the logical type of one value, or None for null (no information)."""
    if value is None:
        return None
    if isinstance(value, bool):  # must come before int: bool is a subclass of int
        return BOOL
    if isinstance(value, int):
        return INT
    if isinstance(value, float):
        return FLOAT
    if isinstance(value, str):
        if _DATETIME_SHAPE.match(value):
            try:
                datetime.fromisoformat(value)
                return DATETIME
            except ValueError:
                return STRING
        return STRING
    return STRING  # lists and objects are stored as JSON text


def merge_types(a: str, b: str) -> str:
    """Widest type that can hold both. int and float widen to float; any other
    disagreement falls back to string."""
    if a == b:
        return a
    if {a, b} == {INT, FLOAT}:
        return FLOAT
    return STRING


def infer_field_type(values: list[Any]) -> str:
    result: str | None = None
    for value in values:
        t = infer_type(value)
        if t is None:
            continue
        result = t if result is None else merge_types(result, t)
    return result or STRING


def validate_field_name(name: str) -> str | None:
    """Returns a rejection reason, or None if the name is acceptable."""
    if name in RESERVED_NAMES:
        return "reserved_name"
    if not _FIELD_NAME.match(name):
        return "invalid_name"
    return None
