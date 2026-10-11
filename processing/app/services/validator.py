import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.models.schemas import CleanEvent, RawEvent


class EventValidationError(Exception):
    """
    Raised when a raw message cannot become a valid event. Carries a short
    machine-readable `error_type` (used for DLQ records and metrics) and a
    human-readable `detail`.
    """

    def __init__(self, error_type: str, detail: str):
        super().__init__(detail)
        self.error_type = error_type
        self.detail = detail


def _summarize(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    )


def parse_raw_event(payload: bytes) -> RawEvent:
    """
    Turns raw Kafka bytes into a validated RawEvent, or raises
    EventValidationError. Each failure mode gets its own error_type so the
    DLQ can be filtered by cause.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EventValidationError("invalid_encoding", str(exc)) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EventValidationError("invalid_json", str(exc)) from exc

    if not isinstance(data, dict):
        raise EventValidationError(
            "invalid_structure",
            f"expected a JSON object, got {type(data).__name__}",
        )

    try:
        return RawEvent.model_validate(data)
    except ValidationError as exc:
        raise EventValidationError("schema_violation", _summarize(exc)) from exc


def normalize_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """
    Cleans property keys: strips whitespace, lowercases, drops empty keys.
    Without this, "Browser", "browser" and " browser " would each look like
    a different new column to the schema detection step.
    """
    cleaned: dict[str, Any] = {}
    for key, value in properties.items():
        normalized = str(key).strip().lower()
        if normalized:
            cleaned[normalized] = value
    return cleaned


def find_unknown_keys(properties: dict[str, Any], known_keys: set[str]) -> list[str]:
    """Returns the property keys not present in the known schema, sorted."""
    return sorted(set(properties) - known_keys)


def build_clean_event(
    event: RawEvent,
    known_keys: set[str],
    now: datetime | None = None,
) -> CleanEvent:
    """
    Normalizes a validated RawEvent and annotates it with any unknown keys.
    `now` is injectable so tests do not depend on the wall clock.
    """
    properties = normalize_properties(event.properties)

    timestamp = event.timestamp
    if timestamp.tzinfo is None:
        # Naive timestamps are assumed to be UTC so ClickHouse gets one convention.
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return CleanEvent(
        event_id=event.event_id,
        event_type=event.event_type.strip().lower(),
        user_id=event.user_id,
        session_id=event.session_id,
        url=event.url,
        timestamp=timestamp,
        properties=properties,
        unknown_keys=find_unknown_keys(properties, known_keys),
        processed_at=now or datetime.now(timezone.utc),
    )