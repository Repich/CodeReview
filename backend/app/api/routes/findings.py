from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
import logging
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.api.utils import ensure_run_access
from backend.app.core.config import get_settings
from backend.app.models.audit import IOLog
from backend.app.models.enums import IODirection, UserRole
from backend.app.models.finding import Finding
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.findings import FindingCreate, FindingList, FindingRead
from backend.app.models.ai_finding import AIFinding
from backend.app.schemas.ai_findings import AIFindingRead
from backend.app.services.norms import build_norm_lookup

router = APIRouter(prefix="/findings", tags=["findings"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@router.get("", response_model=FindingList)
def list_findings(
    review_run_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> FindingList:
    query = db.query(Finding).join(ReviewRun, ReviewRun.id == Finding.review_run_id)
    if review_run_id:
        query = query.filter(Finding.review_run_id == review_run_id)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(ReviewRun.user_id == current_user.id)
    total = query.count()
    db_items = (
        query.order_by(Finding.created_at.desc()).offset(skip).limit(limit).all()
    )
    norm_lookup = build_norm_lookup(db, {item.norm_id for item in db_items})
    items: list[FindingRead] = []
    for item in db_items:
        meta = norm_lookup.get(item.norm_id, {})
        payload = FindingRead.model_validate(item)
        payload.norm_title = meta.get("title")
        payload.norm_text = meta.get("text")
        payload.norm_section = meta.get("section")
        payload.norm_source_reference = meta.get("source_reference")
        payload.norm_source_excerpt = meta.get("source_excerpt")
        items.append(payload)
    return FindingList(total=total, items=items)


@router.post("", response_model=FindingRead, status_code=201)
def create_finding(payload: FindingCreate, db: Session = Depends(get_db)) -> Finding:
    finding = Finding(**payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/{finding_id}", response_model=FindingRead)
def get_finding(
    finding_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> Finding:
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    ensure_run_access(db, finding.review_run_id, current_user)
    return finding


@router.get("/export/{review_run_id}.jsonl")
def export_findings_jsonl(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    ensure_run_access(db, review_run_id, current_user)
    findings = (
        db.query(Finding)
        .filter(Finding.review_run_id == review_run_id)
        .order_by(Finding.created_at.asc())
        .all()
    )
    ai_findings = (
        db.query(AIFinding)
        .filter(AIFinding.review_run_id == review_run_id)
        .order_by(AIFinding.created_at.asc())
        .all()
    )
    if not findings and not ai_findings:
        raise HTTPException(status_code=404, detail="No findings for run")
    settings = get_settings()
    artifact_dir = Path(settings.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    file_path = artifact_dir / f"{review_run_id}_findings.jsonl"
    norm_ids = {item.norm_id for item in findings if item.norm_id}
    norm_ids.update({item.norm_id for item in ai_findings if item.norm_id})
    norm_lookup = build_norm_lookup(db, norm_ids)
    logger.info("Exporting findings for run %s", review_run_id)
    with file_path.open("w", encoding="utf-8") as fh:
        for item in findings:
            payload_model = FindingRead.model_validate(item)
            meta = norm_lookup.get(item.norm_id)
            if meta:
                payload_model.norm_title = meta.get("title")
                payload_model.norm_text = meta.get("text")
                payload_model.norm_section = meta.get("section")
                payload_model.norm_source_reference = meta.get("source_reference")
                payload_model.norm_source_excerpt = meta.get("source_excerpt")
            payload = payload_model.model_dump(mode="json")
            payload["record_type"] = "static"
            if not meta:
                logger.warning("Norm %s not found in DB or norms.yaml", item.norm_id)
            fh.write(json.dumps(payload, ensure_ascii=False))
            fh.write("\n")
        for item in ai_findings:
            payload_model = AIFindingRead.model_validate(item)
            meta = norm_lookup.get(item.norm_id or "")
            if meta:
                payload_model.norm_id = payload_model.norm_id or meta.get("title")
                payload_model.norm_text = payload_model.norm_text or meta.get("text")
                payload_model.section = payload_model.section or meta.get("section")
                payload_model.norm_source_reference = meta.get("source_reference")
                payload_model.norm_source_excerpt = meta.get("source_excerpt")
            payload = payload_model.model_dump(mode="json")
            payload["record_type"] = "ai"
            if not meta and item.norm_id:
                logger.warning("Norm %s not found for AI finding", item.norm_id)
            fh.write(json.dumps(payload, ensure_ascii=False))
            fh.write("\n")
    io_log = IOLog(
        review_run_id=review_run_id,
        direction=IODirection.OUT,
        artifact_type="findings.jsonl",
        storage_path=file_path.name,
        checksum=None,
        size_bytes=file_path.stat().st_size,
    )
    db.add(io_log)
    db.commit()
    return FileResponse(file_path, media_type="application/json", filename=file_path.name)
