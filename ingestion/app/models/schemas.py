from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

class ClickEvent(BaseModel):
    """
    Incoming clickstream event. `properties` is intentionally open-ended —
    any new key that shows up here is exactly what an Intelligence/schema
    service downstream would be responsible for detecting and adding to
    the schema, if this API ever feeds into one.
    """
    event_type: str = Field(..., description="e.g. page_view, click, purchase")
    user_id: str
    session_id: str
    url: str
    timestamp: datetime
    properties: dict[str, Any] = Field(default_factory=dict)

class IngestResponse(BaseModel):
    status: str
    event_id: str
