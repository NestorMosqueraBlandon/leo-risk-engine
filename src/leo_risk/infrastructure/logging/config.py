from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "LEO_", "env_file": ".env", "env_file_encoding": "utf-8"}

    app_name: str = "leo-risk-engine"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000


def get_settings() -> Settings:
    return Settings()
