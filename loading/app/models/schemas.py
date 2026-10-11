from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CleanEvent(BaseModel):
    """Shape of a message on clean_events, as published by Processing."""

    event_id: str
    event_type: str
    user_id: str
    session_id: str
    url: str
    timestamp: datetime
    properties: dict[str, Any] = Field(default_factory=dict)
    unknown_keys: list[str] = Field(default_factory=list)
    processed_at: datetime


class DeadLetterRecord(BaseModel):
    original_payload: str
    error_type: str
    error_detail: str
    source_topic: str
    source_partition: int
    source_offset: int
    failed_at: datetime