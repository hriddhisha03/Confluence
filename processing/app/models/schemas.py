from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class RawEvent(BaseModel):
    """
    Shape of a message on raw_Events, as published by the Ingestion service.
    Ingestion has already validated the base fields, but Processing validates
    again on purpose: any producer can write to the topic, so the consumer
    never trusts the message it reads
    """
    event_id: str
    event_type: str
    user_id: str
    session_id: str
    url: str
    timestamp: datetime
    properties: dict[str, Any] = Field(default_factory=dict)  

class CleanEvent(BaseModel):
    """
    Shape of a message on clean_events. Same fields as RawEvent plus
    processing metadata. `unknown_keys` lists property keys that are not yet
    in the known schema; in Phase 3 a non-empty list triggers the gRPC call
    to the Intelligence service.
    """

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
    """
    Shape of a message on dlq_events. Keeps the original bytes (decoded as
    text) so a bad message can be inspected or replayed later, plus the
    reason and where it came from.
    """

    original_payload: str
    error_type: str
    error_detail: str
    source_topic: str
    source_partition: int
    source_offset: int
    failed_at: datetime  
    
    
