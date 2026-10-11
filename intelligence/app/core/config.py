from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "intelligence"
    log_level: str = "INFO"
    api_port: int = 8001

    postgres_dsn: str = "postgresql://pipeline:pipeline@postgres:5432/schema_registry"

    # Guards against schema bloat: unknown keys become ClickHouse columns, so
    # a producer sending random keys must not be able to create unlimited columns.
    max_new_fields_per_request: int = 50
    max_total_fields: int = 200


settings = Settings()