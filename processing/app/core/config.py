from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "processing"
    log_level: str = "INFO"

    kafka_bootstrap_servers: str = "kafka:9092"

    # Topics
    kafka_raw_events_topic: str = "raw_events"
    kafka_clean_events_topic: str = "clean_events"
    kafka_dlq_topic: str = "dlq_events"

    # Consumer
    kafka_consumer_group: str = "processing-service"
    kafka_auto_offset_reset: str = "earliest"

    # Property keys already in the schema. In Phase 3 this gets loaded from
    # the Postgres schema registry instead of an env var.
    known_property_keys: str = "browser,referrer"

    @property
    def known_property_key_set(self) -> set[str]:
        return {k.strip().lower() for k in self.known_property_keys.split(",") if k.strip()}


settings = Settings()