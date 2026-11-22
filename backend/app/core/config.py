from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums import Severity


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

    # Persistence / Database Configuration
    database_url: SecretStr = SecretStr("")
    checkpointer_backend: Literal["postgres", "memory"] = "memory"

    # GitHub Configuration
    github_webhook_secret: SecretStr = SecretStr("")
    github_token: SecretStr = SecretStr("")
    github_api_url: str = "https://api.github.com"
    github_bot_login: str = ""

    # Azure OpenAI Configuration
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment_strong: str = ""
    azure_openai_deployment_fast: str = ""

    # LLM Configuration
    llm_timeout_seconds: float = 60.0
    llm_max_concurrency: int = 16

    # Review Configuration
    review_chunk_chars: int = 24000
    review_max_chunks: int = 8

    # AI Fixing Configuration
    fix_min_severity: Severity = Severity.MEDIUM
    fix_max_files: int = 5
    fix_max_attempts: int = 3
    fix_max_changed_lines: int = 300
    fix_max_file_chars: int = 60000
    fix_run_tests: bool = True

    # Sandbox Configuration
    sandbox_enabled: bool = False
    sandbox_backend: Literal["docker", "dynamic_sessions"] = "docker"
    sandbox_image: str = "prra-sandbox:latest"
    sandbox_memory_mb: int = 2048
    sandbox_cpus: float = 1.0
    sandbox_pids_limit: int = 512
    sandbox_timeout_seconds: int = 120
    sandbox_test_timeout_seconds: int = 300
    sandbox_max_concurrency: int = 2
    sandbox_workspace_max_mb: int = 200
    sandbox_max_files: int = 20000
    sandbox_max_analyzed_files: int = 200

    # Azure Dynamic Sessions Configuration
    dynamic_sessions_pool_endpoint: str = ""
    dynamic_sessions_api_key: SecretStr = SecretStr("")
    dynamic_sessions_max_session_seconds: int = 300

    # Azure Application Insights & Observability
    applicationinsights_connection_string: SecretStr = SecretStr("")
    telemetry_enabled: bool = True
    telemetry_service_name: str = "pr-review-assistant"


@lru_cache
def get_settings() -> Settings:
    return Settings()
