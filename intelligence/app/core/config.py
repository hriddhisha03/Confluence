from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "intelligence"
    log_level: str = "INFO"
    kafka_bootstrap_servers: str = "kafka:9092"

    class Config:
        env_file = ".env"


settings = Settings()
