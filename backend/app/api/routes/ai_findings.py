from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.api.utils import ensure_run_access
from backend.app.models.ai_finding import AIFinding
from backend.app.models.enums import AIFindingStatus, UserRole
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.ai_findings import (
    AIFindingList,
    AIFindingRead,
    AIFindingUpdate,
)
from backend.app.services.norms import build_norm_lookup

router = APIRouter(prefix="/ai-findings", tags=["ai-findings"])


@router.get("", response_model=AIFindingList)
def list_ai_findings(
    review_run_id: uuid.UUID | None = Query(default=None),
    status: AIFindingStatus | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> AIFindingList:
    query = db.query(AIFinding).join(ReviewRun, ReviewRun.id == AIFinding.review_run_id)
    if review_run_id:
        query = query.filter(AIFinding.review_run_id == review_run_id)
    if status:
        query = query.filter(AIFinding.status == status)
    if current_user.role != UserRole.ADMIN:
        if current_user.company_id:
            query = query.join(UserAccount, UserAccount.id == ReviewRun.user_id).filter(
                UserAccount.company_id == current_user.company_id
            )
        else:
            query = query.filter(ReviewRun.user_id == current_user.id)
    total = query.count()
    rows = query.order_by(AIFinding.created_at.asc()).offset(skip).limit(limit).all()
    norm_lookup = build_norm_lookup(db, {row.norm_id for row in rows if row.norm_id})
    enriched: list[AIFindingRead] = []
    for row in rows:
        payload = AIFindingRead.model_validate(row)
        if row.norm_id:
            meta = norm_lookup.get(row.norm_id)
            if meta:
                payload.section = payload.section or meta.get("section")
                payload.norm_text = payload.norm_text or meta.get("text")
                payload.source_reference = payload.source_reference or meta.get("source_reference")
                payload.norm_source_reference = meta.get("source_reference")
                payload.norm_source_excerpt = meta.get("source_excerpt")
        enriched.append(payload)
    return AIFindingList(total=total, items=enriched)


@router.patch("/{finding_id}", response_model=AIFindingRead)
def update_ai_finding(
    finding_id: uuid.UUID,
    payload: AIFindingUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> AIFinding:
    finding = db.get(AIFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="AI finding not found")
    ensure_run_access(db, finding.review_run_id, current_user, require_owner=True)
    if payload.status is not None:
        finding.status = payload.status
    else:
        raise HTTPException(status_code=400, detail="Status is required")
    if payload.reviewer_comment is not None:
        finding.reviewer_comment = payload.reviewer_comment
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding
