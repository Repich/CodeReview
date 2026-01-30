from __future__ import annotations

from functools import lru_cache
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/codereview"
    project_name: str = "CodeReview API"
    api_prefix: str = "/api"
    debug: bool = False
    artifact_dir: str = "artifact_storage"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    default_run_cost_points: int = 10
    auth_jwt_secret: str = "insecure-dev-secret"
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 60 * 24
    admin_local_only: bool = True
    admin_allowed_cidrs: list[str] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ]
    auth_failed_login_limit: int = 5
    auth_failed_login_window_minutes: int = 15
    registration_rate_limit: int = 5
    registration_rate_window_minutes: int = 60
    registration_bonus_points: int = 100
    turnstile_secret_key: str | None = None
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    caddy_log_ingest_token: str | None = None
    caddy_log_retention_days: int = 30
    access_log_enabled: bool = True
    trusted_proxy_depth: int = 1
    blocked_ips: list[str] = []
    blocked_cidrs: list[str] = []
    blocked_countries: list[str] = []
    geoip_db_path: str | None = None
    db_pool_size: int = 15
    db_max_overflow: int = 30
    db_pool_timeout_seconds: int = 30
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_reasoning_model: str = "deepseek-reasoner"
    llm_timeout_seconds: int = 60
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CODEREVIEW_", extra="ignore")


class HealthInfo(BaseModel):
    version: str
    engine_version: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
