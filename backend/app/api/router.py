from __future__ import annotations

from fastapi import APIRouter

import backend.app.api.routes.admin_review_runs as admin_review_runs
import backend.app.api.routes.ai_findings as ai_findings
import backend.app.api.routes.auth as auth
import backend.app.api.routes.audit as audit
import backend.app.api.routes.access_logs as access_logs
import backend.app.api.routes.caddy_logs as caddy_logs
import backend.app.api.routes.companies as companies
import backend.app.api.routes.feedback as feedback
import backend.app.api.routes.findings as findings
import backend.app.api.routes.changelog as changelog
import backend.app.api.routes.health as health
import backend.app.api.routes.llm_playground as llm_playground
import backend.app.api.routes.model_lab as model_lab
import backend.app.api.routes.norms as norms
import backend.app.api.routes.open_world_candidates as open_world_candidates
import backend.app.api.routes.review_runs as review_runs
import backend.app.api.routes.users as users
import backend.app.api.routes.wallets as wallets
import backend.app.api.routes.suggested_norms as suggested_norms

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai_findings.router)
api_router.include_router(open_world_candidates.router)
api_router.include_router(norms.router)
api_router.include_router(suggested_norms.router)
api_router.include_router(review_runs.router)
api_router.include_router(findings.router)
api_router.include_router(feedback.router)
api_router.include_router(audit.router)
api_router.include_router(users.router)
api_router.include_router(changelog.router)
api_router.include_router(companies.router)
api_router.include_router(wallets.router)
api_router.include_router(access_logs.router)
api_router.include_router(caddy_logs.router)
api_router.include_router(admin_review_runs.router)
api_router.include_router(llm_playground.router)
api_router.include_router(model_lab.router)
