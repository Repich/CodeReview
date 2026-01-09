from __future__ import annotations

from backend.app.schemas.base import ORMModel


class HealthResponse(ORMModel):
    status: str = "ok"
    engine_version: str
