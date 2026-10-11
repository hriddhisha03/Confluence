from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_name: str = "ingestion"
    log_level: str = "INFO"
    api_port: int = 8000
    
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_raw_events_topic: str = "raw_events"
    
    auth_api_keys: str = "dev-key-123"
    
    class Config:
        env_file = ".env"
    
    @property
    def valid_api_keys(self) -> set[str]:
        return {k.strip() for k in self.auth_api_keys.split(",") if k.strip()}
settings = Settings()
    