from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.core.config import get_settings
from backend.app.models.audit import AuditLog
from backend.app.models.enums import AuditEventType, ReviewStatus
from backend.app.models.model_lab import ModelLabCase, ModelLabSession
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.model_lab import (
    ModelLabConfigRead,
    ModelLabDiscoverRequest,
    ModelLabDiscoverResponse,
    ModelLabEvaluateRequest,
    ModelLabSessionCreate,
    ModelLabSessionDetail,
    ModelLabSessionRead,
)
from backend.app.schemas.tasks import AnalysisTaskResponse, SourceUnitPayload
from backend.app.schemas.users import UserSettings
from backend.app.services import artifacts as artifact_service
from backend.app.services.model_lab import (
    create_session,
    evaluate_session,
    get_session_detail,
    handle_case_result,
    list_sessions,
    mark_case_started,
)
from backend.app.services.model_lab_llm import ModelLabLLMError, discover_models
from backend.app.services.model_lab_secrets import get_secret

router = APIRouter(prefix="/admin/model-lab", tags=["admin-model-lab"])


class ModelLabRunFailPayload(BaseModel):
    error_message: str = Field(..., min_length=1, max_length=4000)


@router.get("/config", response_model=ModelLabConfigRead)
def get_model_lab_config(
    current_admin: UserAccount = Depends(get_current_admin),
) -> ModelLabConfigRead:
    _ = current_admin
    settings = get_settings()
    return ModelLabConfigRead(
        enabled=settings.model_lab_enabled,
        default_sample_size=settings.model_lab_default_sample_size,
        max_sample_size=settings.model_lab_max_sample_size,
        max_models=settings.model_lab_max_models,
        max_paid_target_models=settings.model_lab_max_paid_target_models,
        max_paid_target_runs=settings.model_lab_max_paid_target_runs,
        max_expert_models=settings.model_lab_max_expert_models,
        max_expert_calls=settings.model_lab_max_expert_calls,
    )


@router.post("/discover-models", response_model=ModelLabDiscoverResponse)
def discover_internal_models(
    payload: ModelLabDiscoverRequest,
    current_admin: UserAccount = Depends(get_current_admin),
) -> ModelLabDiscoverResponse:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    try:
        models = discover_models(
            api_base=payload.api_base,
            api_key=payload.api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    except ModelLabLLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModelLabDiscoverResponse(models=models)


def _fail_review_run(
    db: Session,
    *,
    review_run: ReviewRun,
    reason: str,
    artifact_path: str | None = None,
) -> None:
    review_run.status = ReviewStatus.FAILED
    review_run.finished_at = datetime.utcnow()
    db.add(review_run)
    payload: dict[str, str] = {"reason": reason}
    if artifact_path:
        payload["artifact"] = artifact_path
    db.add(
        AuditLog(
            review_run_id=review_run.id,
            event_type=AuditEventType.RUN_FAILED,
            payload=payload,
        )
    )
    db.commit()
    handle_case_result(
        db,
        review_run=review_run,
        findings_count=0,
        ai_findings_count=0,
        open_world_count=0,
        duration_ms=0,
    )


def _resolve_settings_payload(db: Session, *, review_run: ReviewRun) -> dict | None:
    settings_payload: dict | None = None
    if review_run.user_id:
        user = db.get(UserAccount, review_run.user_id)
        if user and isinstance(user.settings, dict):
            settings_payload = UserSettings.model_validate(user.settings).model_dump()
    ctx = review_run.context or {}
    worker_override = ctx.get("worker_settings_override")
    if not isinstance(worker_override, dict):
        return settings_payload
    merged_settings = dict(settings_payload or {})
    for key, value in worker_override.items():
        if key == "llm_api_key_ref":
            secret = get_secret(str(value))
            if not secret:
                raise ValueError("model_lab_secret_missing")
            merged_settings["llm_api_key"] = secret
            continue
        merged_settings[key] = value
    return merged_settings


@router.get(
    "/sessions/{session_id}/internal-next-task",
    response_model=AnalysisTaskResponse | None,
)
def fetch_next_internal_task(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> AnalysisTaskResponse | Response:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    session = db.get(ModelLabSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Model Lab session not found")

    while True:
        row = (
            db.query(ModelLabCase, ReviewRun)
            .join(ReviewRun, ReviewRun.id == ModelLabCase.review_run_id)
            .filter(
                ModelLabCase.session_id == session_id,
                ModelLabCase.target_provider == "internal",
                ReviewRun.status == ReviewStatus.QUEUED,
            )
            .order_by(ModelLabCase.created_at.asc())
            .with_for_update(of=ReviewRun, skip_locked=True)
            .first()
        )
        if not row:
            return Response(status_code=204)
        _, review_run = row
        ctx = review_run.context or {}
        artifact_path = ctx.get("source_artifact")
        if not artifact_path:
            _fail_review_run(db, review_run=review_run, reason="missing_source_artifact")
            continue
        try:
            sources = artifact_service.load_sources(artifact_path)
        except FileNotFoundError:
            _fail_review_run(
                db,
                review_run=review_run,
                reason="missing_source_file",
                artifact_path=artifact_path,
            )
            continue
        try:
            settings_payload = _resolve_settings_payload(db, review_run=review_run)
        except ValueError:
            _fail_review_run(db, review_run=review_run, reason="model_lab_secret_missing")
            continue

        review_run.status = ReviewStatus.RUNNING
        if not review_run.started_at:
            review_run.started_at = datetime.utcnow()
        db.add(review_run)
        db.add(
            AuditLog(
                review_run_id=review_run.id,
                event_type=AuditEventType.WORKER_STARTED,
                payload={"artifact": artifact_path, "worker": "model_lab_internal_bridge"},
            )
        )
        db.commit()
        mark_case_started(db, review_run)
        return AnalysisTaskResponse(
            review_run_id=review_run.id,
            sources=[SourceUnitPayload(**source) for source in sources],
            settings=settings_payload,
            context=review_run.context,
        )


@router.post("/review-runs/{review_run_id}/fail", status_code=204)
def mark_model_lab_run_failed(
    review_run_id: uuid.UUID,
    payload: ModelLabRunFailPayload,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> Response:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    ctx = review_run.context or {}
    if not ctx.get("model_lab_case_id"):
        raise HTTPException(status_code=400, detail="Review run is not a model-lab case")
    _fail_review_run(
        db,
        review_run=review_run,
        reason="model_lab_internal_runner_failed",
        artifact_path=None,
    )
    case = db.query(ModelLabCase).filter(ModelLabCase.review_run_id == review_run_id).first()
    if case:
        case.error_message = payload.error_message
        db.add(case)
        db.commit()
    return Response(status_code=204)


@router.post("/sessions", response_model=ModelLabSessionRead, status_code=201)
def create_model_lab_session(
    payload: ModelLabSessionCreate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> ModelLabSessionRead:
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    try:
        session = create_session(db, payload=payload, current_admin=current_admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelLabSessionRead.model_validate(session)


@router.get("/sessions", response_model=list[ModelLabSessionRead])
def list_model_lab_sessions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> list[ModelLabSessionRead]:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    rows = list_sessions(db, limit=limit)
    return [ModelLabSessionRead.model_validate(item) for item in rows]


@router.get("/sessions/{session_id}", response_model=ModelLabSessionDetail)
def get_model_lab_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> ModelLabSessionDetail:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    try:
        return get_session_detail(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/evaluate", response_model=ModelLabSessionDetail)
def evaluate_model_lab_session(
    session_id: uuid.UUID,
    payload: ModelLabEvaluateRequest,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> ModelLabSessionDetail:
    _ = current_admin
    settings = get_settings()
    if not settings.model_lab_enabled:
        raise HTTPException(status_code=404, detail="Model Lab disabled")
    try:
        return evaluate_session(db, session_id=session_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
