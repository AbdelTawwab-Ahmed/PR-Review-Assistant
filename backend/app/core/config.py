from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PR-Review-Assistant"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]

    redis_url: str = "redis://localhost:6379/0"
    cache_backend: Literal["redis", "memory"] = "redis"
    cache_ttl_seconds: int = 86400

    github_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
