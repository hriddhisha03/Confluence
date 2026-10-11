import json

from pydantic import ValidationError

from app.models.schemas import CleanEvent

# Order matters: to_row() returns values in exactly this order.
# received_at is left out on purpose so ClickHouse fills it from its DEFAULT.
COLUMNS: tuple[str, ...] = (
    "event_id",
    "event_type",
    "user_id",
    "session_id",
    "url",
    "timestamp",
    "raw_payload",
)


class EventParseError(Exception):
    def __init__(self, error_type: str, detail: str):
        super().__init__(detail)
        self.error_type = error_type
        self.detail = detail


def parse_clean_event(payload: bytes) -> CleanEvent:
    """Processing should only publish valid events, but Loading never trusts
    the topic: anything unparseable becomes an EventParseError."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EventParseError("invalid_encoding", str(exc)) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EventParseError("invalid_json", str(exc)) from exc

    try:
        return CleanEvent.model_validate(data)
    except ValidationError as exc:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise EventParseError("schema_violation", detail) from exc


def to_row(event: CleanEvent) -> list:
    """Maps an event to one ClickHouse row. Until the schema evolution steps
    are built, all properties are stored as a JSON string in raw_payload."""
    return [
        event.event_id,
        event.event_type,
        event.user_id,
        event.session_id,
        event.url,
        event.timestamp,
        json.dumps(event.properties, separators=(",", ":"), sort_keys=True),
    ]