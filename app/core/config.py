from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TraceCore Decision Engine"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://tracecore:tracecore@localhost:5432/tracecore"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    rate_limit_per_minute: int = 30
    cache_ttl_seconds: int = 900
    mock_llm_enabled: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

