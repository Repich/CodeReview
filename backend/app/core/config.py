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
    access_log_enabled: bool = True
    trusted_proxy_depth: int = 1
    blocked_ips: list[str] = []
    blocked_cidrs: list[str] = []
    blocked_countries: list[str] = []
    geoip_db_path: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CODEREVIEW_", extra="ignore")


class HealthInfo(BaseModel):
    version: str
    engine_version: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
