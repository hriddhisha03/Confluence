from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "loading"
    log_level: str = "INFO"

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_clean_events_topic: str = "clean_events"
    kafka_dlq_topic: str = "dlq_events"
    kafka_consumer_group: str = "loading-service"
    kafka_auto_offset_reset: str = "earliest"

    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"
    clickhouse_table: str = "click_events"

    # A batch is flushed when it reaches batch_size rows OR when
    # batch_interval_seconds have passed, whichever happens first.
    batch_size: int = 1000
    batch_interval_seconds: float = 2.0

    insert_max_retries: int = 3
    insert_retry_backoff_seconds: float = 1.0


settings = Settings()