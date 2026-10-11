from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_producer: AIOKafkaProducer | None = None

async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await _producer.start()
    logger.info("kafka_producer_started", bootstrap_servers=settings.kafka_bootstrap_servers)
   
async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        logger.info("kafka_producer_stopped") 
        _producer = None
async def publish_raw_event(key:str, value:bytes) -> None:
    if _producer is None:
        raise RuntimeError("Kafka producer not started")
    await _producer.send_and_wait(settings.kafka_raw_events_topic, key=key.encode("utf-8"), value=value)
