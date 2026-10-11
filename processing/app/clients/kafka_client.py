from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import settings

from app.core.logging import get_logger
logger = get_logger(__name__)

_consumer: AIOKafkaConsumer | None = None
_producer: AIOKafkaProducer| None = None

async def start_kafka() -> None:
    """Starts the consumer on raw event and one shared producer for clean_events and dlq_events."""
    global _consumer, _producer
    
    _producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    await _producer.start()
    
    _consumer = AIOKafkaConsumer(
        settings.kafka_raw_events_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset=settings.kafka_auto_offset_reset,
        enable_auto_commit=False, 
    )
    await _consumer.start()
    
    logger.info(
        "kafka_started",
        topic=settings.kafka_raw_events_topic,
        group=settings.kafka_consumer_group
    )

async def stop_kafka() -> None:
    global _consumer, _producer
    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
    if _producer is not None:
        await _producer.stop()
        _producer = None
    logger.info("kafka_stopped")


def get_consumer() -> AIOKafkaConsumer:
    if _consumer is None:
        raise RuntimeError("Kafka consumer not started")
    return _consumer


async def publish(topic: str, key: bytes | None, value: bytes) -> None:
    if _producer is None:
        raise RuntimeError("Kafka producer not started")
    await _producer.send_and_wait(topic, key=key, value=value)


async def commit() -> None:
    await get_consumer().commit()