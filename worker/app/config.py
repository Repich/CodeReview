from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_api_url: str = "http://backend:8000/api"
    redis_url: str = "redis://localhost:6379/0"
    poll_interval_seconds: int = 5
    engine_version: str = "0.1.0"
    detectors_version: str = "dev"
    norms_version: str = "n/a"
    llm_provider: str = "deepseek"
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 60
    llm_context_glob: str | None = None
    model_config = SettingsConfigDict(
        env_prefix="CODEREVIEW_WORKER_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
