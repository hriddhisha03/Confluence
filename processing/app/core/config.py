from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "processing"
    log_level: str = "INFO"
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_raw_events_topic: str = "raw_events"
    kafka_clean_events_topic: str = "clean_events"
    kafka_dlq_topic: str = "dlq_events"
    kafka_schema_updates_topic: str = "schema_updates"
    kafka_consumer_group: str = "processing-service"
    kafka_auto_offset_reset: str = "earliest"
    known_property_keys: str = "browser,referrer"

    postgres_dsn: str = "postgresql://pipeline:pipeline@postgres:5432/schema_registry"
    known_keys_refresh_seconds: float = 10.0

    intelligence_url: str = "http://intelligence:8001"
    intelligence_timeout_seconds: float = 2.0
    # After a failed call, Intelligence is not called again for this long, so a
    # slow or down service cannot stall the consumer on every single event.
    intelligence_cooldown_seconds: float = 10.0
    # Keys Intelligence refused (invalid name, limits) are remembered in
    # memory so they are not sent again. Bounded to cap memory use.
    rejected_keys_max: int = 10000

    @property
    def known_property_key_set(self) -> set[str]:
        return {k.strip().lower() for k in self.known_property_keys.split(",") if k.strip()}


settings = Settings()