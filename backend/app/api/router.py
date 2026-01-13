from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import (
    admin_review_runs,
    ai_findings,
    auth,
    audit,
    access_logs,
    caddy_logs,
    feedback,
    findings,
    health,
    norms,
    review_runs,
    users,
    wallets,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai_findings.router)
api_router.include_router(norms.router)
api_router.include_router(review_runs.router)
api_router.include_router(findings.router)
api_router.include_router(feedback.router)
api_router.include_router(audit.router)
api_router.include_router(users.router)
api_router.include_router(wallets.router)
api_router.include_router(access_logs.router)
api_router.include_router(caddy_logs.router)
api_router.include_router(admin_review_runs.router)
