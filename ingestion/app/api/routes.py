import json
import uuid

from fastapi import APIRouter, Depends

from app.clients.kafka_client import publish_raw_event
from app.core.logging import get_logger
from app.core.security import verify_api_key
from app.models.schemas import ClickEvent, IngestResponse

logger = get_logger(__name__)
router = APIRouter()

@router.post("/events", response_model=IngestResponse, status_code=202)
async def ingest_event(event: ClickEvent, _: str = Depends(verify_api_key)):
    """
    Accepts one clickstream event, stamps it with a server-side event_id,
    and publishes it to Kafka. Returns 202 Accepted immediately — this
    service does not wait for downstream processing, by design.
    """
    event_id = str(uuid.uuid4())
    payload = event.model_dump(mode="json")
    payload["event_id"] = event_id
    
    await publish_raw_event(key=event.session_id, value=json.dumps(payload).encode("utf-8"))    
    logger.info("event_ingested", event_id=event_id, event_type=event.event_type)
    return IngestResponse(status="accepted", event_id=event_id)