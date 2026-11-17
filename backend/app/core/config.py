
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PR-Review-Assistant"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Redis and Cache Configuration
    redis_url: str = "redis://localhost:6379/0"
    cache_backend: Literal["redis", "memory"] = "redis"
    cache_ttl_seconds: int = 86400

    # GitHub Configuration
    github_webhook_secret: SecretStr = SecretStr("")
    github_token: SecretStr = SecretStr("")
    github_api_url: str = "https://api.github.com"
    github_bot_login: str = ""

    # Azure OpenAI Configuration
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment_strong: str = ""
    azure_openai_deployment_fast: str = ""

    # LLM Configuration
    llm_timeout_seconds: float = 60.0
    llm_max_concurrency: int = 4

    # Review Configuration
    review_chunk_chars: int = 24000
    review_max_chunks: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
