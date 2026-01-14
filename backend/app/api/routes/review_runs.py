from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.api.utils import ensure_run_access
from backend.app.models.ai_finding import AIFinding
from backend.app.models.audit import AuditLog, IOLog
from backend.app.models.finding import Finding
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.models.enums import (
    AIFindingStatus,
    AuditEventType,
    IODirection,
    ReviewStatus,
    UserRole,
)
from backend.app.schemas.review_runs import (
    ReviewRunCreate,
    ReviewRunRead,
    ReviewRunUpdate,
    SourceChangePayload,
)
from backend.app.schemas.tasks import (
    AnalysisResultPayload,
    AnalysisTaskResponse,
    SourceUnitPayload,
)
from backend.app.schemas.tasks import LineRangePayload
from backend.app.schemas.llm import LLMLogEntry
from backend.app.services import artifacts as artifact_service, billing
from backend.app.services.diff_parser import parse_crucible_diff, merge_change_ranges
from backend.app.core.config import get_settings

router = APIRouter(prefix="/review-runs", tags=["review-runs"])


@router.get("", response_model=list[ReviewRunRead])
def list_review_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[ReviewRunRead]:
    query = (
        db.query(ReviewRun, UserAccount)
        .outerjoin(UserAccount, UserAccount.id == ReviewRun.user_id)
        .order_by(ReviewRun.queued_at.desc())
    )
    if current_user.role != UserRole.ADMIN:
        query = query.filter(ReviewRun.user_id == current_user.id)
    elif user_id:
        query = query.filter(ReviewRun.user_id == user_id)
    rows = query.offset(skip).limit(limit).all()
    payloads: list[ReviewRunRead] = []
    for review_run, user in rows:
        payload = ReviewRunRead.model_validate(review_run)
        payload.user_email = user.email if user else None
        payload.user_name = user.name if user else None
        payloads.append(payload)
    return payloads


@router.post("", response_model=ReviewRunRead, status_code=201)
def create_review_run(
    payload: ReviewRunCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ReviewRun:
    settings = get_settings()
    data = payload.model_dump(exclude={"sources", "changes"}, exclude_none=True)
    context = data.get("context") or {}
    run_id = uuid.uuid4()
    data["id"] = run_id
    data["user_id"] = current_user.id
    data["cost_points"] = settings.default_run_cost_points

    raw_sources = payload.sources or []
    processed_sources: list[SourceUnitPayload] = []
    for source in raw_sources:
        content, ranges = parse_crucible_diff(source.content)
        source.content = content
        if ranges:
            source.change_ranges = [
                LineRangePayload(start=start, end=end) for start, end in ranges
            ]
        processed_sources.append(source)

    change_map = _build_change_map(processed_sources, payload.changes or [])
    if change_map:
        merged_ctx = dict(context)
        merged_ctx["change_ranges"] = change_map
        context = merged_ctx

    artifact_payload: tuple[str, str, int] | None = None
    sources_payload: list[dict] = []
    if processed_sources:
        sources_payload = [source.model_dump() for source in processed_sources]
        artifact_payload = artifact_service.save_sources(str(run_id), sources_payload)
        ctx = dict(context)
        ctx["source_artifact"] = artifact_payload[0]
        context = ctx

    if context:
        data["context"] = context

    review_run = ReviewRun(**data)
    review_run.status = ReviewStatus.QUEUED
    try:
        billing.charge_for_run(db, current_user, settings.default_run_cost_points, run_id)
    except HTTPException:
        db.rollback()
        raise
    db.add(review_run)
    db.commit()
    db.refresh(review_run)

    if artifact_payload:
        rel_path, checksum, size = artifact_payload
        db.add(
            IOLog(
                review_run_id=review_run.id,
                direction=IODirection.IN,
                artifact_type="sources.json",
                storage_path=rel_path,
                checksum=checksum,
                size_bytes=size,
            )
        )
        db.add(
            AuditLog(
                review_run_id=review_run.id,
                event_type=AuditEventType.RUN_CREATED,
                payload={"sources": len(sources_payload)},
            )
        )
        db.commit()
    return review_run


@router.get("/next-task", response_model=AnalysisTaskResponse | None)
def fetch_next_task(response: Response, db: Session = Depends(get_db)):
    while True:
        review_run = (
            db.query(ReviewRun)
            .filter(ReviewRun.status == ReviewStatus.QUEUED)
            .order_by(ReviewRun.queued_at.asc())
            .first()
        )
        if not review_run:
            return Response(status_code=204)
        ctx = review_run.context or {}
        artifact_path = ctx.get("source_artifact")
        if not artifact_path:
            review_run.status = ReviewStatus.FAILED
            review_run.finished_at = datetime.utcnow()
            db.add(review_run)
            db.add(
                AuditLog(
                    review_run_id=review_run.id,
                    event_type=AuditEventType.RUN_FAILED,
                    payload={"reason": "missing_source_artifact"},
                )
            )
            db.commit()
            continue
        try:
            sources = artifact_service.load_sources(artifact_path)
        except FileNotFoundError:
            review_run.status = ReviewStatus.FAILED
            review_run.finished_at = datetime.utcnow()
            db.add(review_run)
            db.add(
                AuditLog(
                    review_run_id=review_run.id,
                    event_type=AuditEventType.RUN_FAILED,
                    payload={"reason": "missing_source_file", "artifact": artifact_path},
                )
            )
            db.commit()
            continue
        review_run.status = ReviewStatus.RUNNING
        if not review_run.started_at:
            review_run.started_at = datetime.utcnow()
        db.add(review_run)
        db.add(
            AuditLog(
                review_run_id=review_run.id,
                event_type=AuditEventType.WORKER_STARTED,
                payload={"artifact": artifact_path},
            )
        )
        db.commit()
        return AnalysisTaskResponse(
            review_run_id=review_run.id,
            sources=[SourceUnitPayload(**source) for source in sources],
        )


@router.post("/{review_run_id}/results")
def submit_results(
    review_run_id: uuid.UUID,
    payload: AnalysisResultPayload,
    db: Session = Depends(get_db),
):
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    review_run.engine_version = payload.engine_version
    review_run.detectors_version = payload.detectors_version
    review_run.norms_version = payload.norms_version
    if payload.llm_prompt_version is not None:
        review_run.llm_prompt_version = payload.llm_prompt_version
    if payload.metrics:
        context = dict(review_run.context or {})
        metrics = dict(context.get("metrics") or {})
        for key, value in payload.metrics.items():
            metrics[key] = value
        context["metrics"] = metrics
        review_run.context = context
    review_run.status = ReviewStatus.COMPLETED
    review_run.started_at = review_run.started_at or datetime.utcnow()
    review_run.finished_at = datetime.utcnow()
    db.add(review_run)

    for finding_payload in payload.findings:
        finding = Finding(
            review_run_id=review_run.id,
            norm_id=finding_payload.norm_id,
            detector_id=finding_payload.detector_id,
            severity=finding_payload.severity,
            file_path=finding_payload.file_path,
            line_start=finding_payload.line_start,
            line_end=finding_payload.line_end,
            column_start=finding_payload.column_start,
            column_end=finding_payload.column_end,
            message=finding_payload.message,
            recommendation=finding_payload.recommendation,
            code_snippet=finding_payload.code_snippet,
            context=finding_payload.context,
        )
        db.add(finding)
    ai_count = 0
    for ai_payload in payload.ai_findings or []:
        ai_finding = AIFinding(
            review_run_id=review_run.id,
            status=AIFindingStatus.SUGGESTED,
            norm_id=ai_payload.norm_id,
            section=ai_payload.section,
            category=ai_payload.category,
            severity=ai_payload.severity,
            norm_text=ai_payload.norm_text,
            source_reference=ai_payload.source_reference,
            reviewer_comment=None,
            evidence=ai_payload.evidence,
            llm_raw_response=ai_payload.llm_raw_response,
        )
        db.add(ai_finding)
        ai_count += 1

    llm_log_count = 0
    for idx, log_payload in enumerate(payload.llm_logs or []):
        rel_path, size = artifact_service.save_llm_log(
            str(review_run.id),
            idx,
            log_payload.model_dump(),
        )
        io_log = IOLog(
            review_run_id=review_run.id,
            direction=IODirection.OUT,
            artifact_type="llm_log.json",
            storage_path=rel_path,
            checksum=None,
            size_bytes=size,
        )
        db.add(io_log)
        llm_log_count += 1

    db.add(
        AuditLog(
            review_run_id=review_run.id,
            event_type=AuditEventType.WORKER_COMPLETED,
            payload={
                "findings": len(payload.findings),
                "ai_findings": ai_count,
                "llm_logs": llm_log_count,
                "duration_ms": payload.duration_ms,
            },
        )
    )
    db.commit()
    return {"findings": len(payload.findings)}


@router.get("/{review_run_id}/llm/logs", response_model=list[LLMLogEntry])
def list_llm_logs(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[LLMLogEntry]:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can access LLM logs")
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    logs = (
        db.query(IOLog)
        .filter(
            IOLog.review_run_id == review_run_id,
            IOLog.artifact_type == "llm_log.json",
        )
        .order_by(IOLog.created_at.asc())
        .all()
    )
    entries: list[LLMLogEntry] = []
    for log in logs:
        data = artifact_service.load_json(log.storage_path)
        entries.append(
            LLMLogEntry(
                io_log_id=log.id,
                created_at=log.created_at,
                artifact_type=log.artifact_type,
                data=data,
            )
        )
    return entries


@router.get("/{review_run_id}", response_model=ReviewRunRead)
def get_review_run(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ReviewRun:
    review_run = ensure_run_access(db, review_run_id, current_user)
    return review_run


@router.patch("/{review_run_id}", response_model=ReviewRunRead)
def update_review_run(
    review_run_id: uuid.UUID,
    payload: ReviewRunUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ReviewRun:
    review_run = ensure_run_access(db, review_run_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review_run, field, value)
    db.add(review_run)
    db.commit()
    db.refresh(review_run)
    return review_run


@router.post("/{review_run_id}/rerun", response_model=ReviewRunRead)
def rerun_review_run(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ReviewRun:
    review_run = ensure_run_access(db, review_run_id, current_user)
    if review_run.status in (ReviewStatus.RUNNING, ReviewStatus.QUEUED):
        raise HTTPException(status_code=409, detail="Запуск уже выполняется или ожидает")

    ctx = review_run.context or {}
    artifact_path = ctx.get("source_artifact")
    if not artifact_path:
        raise HTTPException(status_code=409, detail="Невозможно перезапустить: нет исходников")
    settings = get_settings()
    source_file = Path(settings.artifact_dir) / artifact_path
    if not source_file.exists():
        raise HTTPException(status_code=409, detail="Невозможно перезапустить: источник не найден")

    db.query(Finding).filter(Finding.review_run_id == review_run.id).delete(
        synchronize_session=False
    )
    db.query(AIFinding).filter(AIFinding.review_run_id == review_run.id).delete(
        synchronize_session=False
    )
    db.query(AuditLog).filter(
        AuditLog.review_run_id == review_run.id,
        AuditLog.event_type != AuditEventType.RUN_CREATED,
    ).delete(synchronize_session=False)

    output_logs = (
        db.query(IOLog)
        .filter(IOLog.review_run_id == review_run.id, IOLog.direction == IODirection.OUT)
        .all()
    )
    for record in output_logs:
        artifact_service.delete_artifact(record.storage_path)
    db.query(IOLog).filter(
        IOLog.review_run_id == review_run.id,
        IOLog.direction == IODirection.OUT,
    ).delete(synchronize_session=False)

    review_run.status = ReviewStatus.QUEUED
    review_run.queued_at = datetime.utcnow()
    review_run.started_at = None
    review_run.finished_at = None
    review_run.engine_version = None
    review_run.detectors_version = None
    review_run.norms_version = None
    review_run.llm_prompt_version = None
    db.add(review_run)
    db.commit()
    db.refresh(review_run)
    return review_run


@router.delete("/{review_run_id}", status_code=204)
def delete_review_run(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    review_run = ensure_run_access(db, review_run_id, current_user)
    if review_run.status == ReviewStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Нельзя удалить запуск, который выполняется")

    artifact_service.delete_run_artifacts(str(review_run.id))

    db.query(Finding).filter(Finding.review_run_id == review_run.id).delete(
        synchronize_session=False
    )
    db.query(AIFinding).filter(AIFinding.review_run_id == review_run.id).delete(
        synchronize_session=False
    )
    db.query(AuditLog).filter(AuditLog.review_run_id == review_run.id).delete(
        synchronize_session=False
    )
    db.query(IOLog).filter(IOLog.review_run_id == review_run.id).delete(synchronize_session=False)
    db.delete(review_run)
    db.commit()


@router.get("/{review_run_id}/sources")
def get_review_run_sources(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    review_run = ensure_run_access(db, review_run_id, current_user)
    ctx = review_run.context or {}
    artifact_path = ctx.get("source_artifact")
    if not artifact_path:
        raise HTTPException(status_code=404, detail="Sources are not available for this run")
    sources = artifact_service.load_sources(artifact_path)
    change_map = ctx.get("change_ranges") or {}
    enriched = []
    for source in sources:
        path = source.get("path")
        enriched.append(
            {
                "path": path,
                "name": source.get("name"),
                "module_type": source.get("module_type"),
                "content": source.get("content"),
                "change_ranges": change_map.get(path, []),
            }
        )
    return enriched


def _build_change_map(
    sources: list[SourceUnitPayload], extra_changes: list[SourceChangePayload]
) -> dict[str, list[dict[str, int]]]:
    change_map: dict[str, list[dict[str, int]]] = {}
    for source in sources:
        if not source.change_ranges:
            continue
        change_map[source.path] = [
            {"start": start, "end": end}
            for start, end in merge_change_ranges(
                [_get_range_tuple(range_item) for range_item in source.change_ranges]
            )
        ]
    for change in extra_changes:
        existing = change_map.setdefault(change.path, [])
        existing.extend(
            {"start": start, "end": end} for start, end in (_get_range_tuple(item) for item in change.ranges)
        )
        merged = merge_change_ranges([(item["start"], item["end"]) for item in existing if item])
        change_map[change.path] = [{"start": start, "end": end} for start, end in merged]
    return change_map


def _get_range_tuple(range_item: LineRangePayload | dict | tuple | list) -> tuple[int, int]:
    if hasattr(range_item, "start") and hasattr(range_item, "end"):
        return int(range_item.start), int(range_item.end)
    if isinstance(range_item, dict):
        return int(range_item["start"]), int(range_item["end"])
    if isinstance(range_item, (list, tuple)) and len(range_item) == 2:
        return int(range_item[0]), int(range_item[1])
    raise ValueError(f"Invalid range item: {range_item!r}")
