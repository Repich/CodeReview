from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.version import ENGINE_VERSION
from backend.app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def read_health() -> HealthResponse:
    return HealthResponse(engine_version=ENGINE_VERSION)
