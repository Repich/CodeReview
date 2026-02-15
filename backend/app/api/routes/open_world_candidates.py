from __future__ import annotations

import uuid

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_current_teacher, get_db
from backend.app.api.utils import ensure_run_access
from backend.app.models.enums import UserRole
from backend.app.models.open_world_candidate import OpenWorldCandidate
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.open_world_candidates import (
    OpenWorldCandidateAccept,
    OpenWorldCandidateList,
    OpenWorldCandidateRead,
)
from backend.app.services.norms import load_custom_norms
from backend.app.services.norms import build_norm_lookup
from backend.app.services.suggested_norms import append_norm_to_yaml_file

router = APIRouter(prefix="/open-world-candidates", tags=["open-world-candidates"])


@router.get("", response_model=OpenWorldCandidateList)
def list_open_world_candidates(
    review_run_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> OpenWorldCandidateList:
    query = db.query(OpenWorldCandidate).join(
        ReviewRun, ReviewRun.id == OpenWorldCandidate.review_run_id
    )
    if review_run_id:
        ensure_run_access(db, review_run_id, current_user)
        query = query.filter(OpenWorldCandidate.review_run_id == review_run_id)
    else:
        if current_user.role != UserRole.ADMIN:
            if current_user.company_id:
                query = query.join(UserAccount, UserAccount.id == ReviewRun.user_id).filter(
                    UserAccount.company_id == current_user.company_id
                )
            else:
                query = query.filter(ReviewRun.user_id == current_user.id)
    total = query.count()
    rows = query.order_by(OpenWorldCandidate.created_at.asc()).offset(skip).limit(limit).all()

    norm_ids = {row.mapped_norm_id for row in rows if row.mapped_norm_id}
    norm_ids.update({row.accepted_norm_id for row in rows if row.accepted_norm_id})
    norm_lookup = build_norm_lookup(db, norm_ids)
    items: list[OpenWorldCandidateRead] = []
    for row in rows:
        payload = OpenWorldCandidateRead.model_validate(row)
        lookup_id = row.accepted_norm_id or row.mapped_norm_id
        if lookup_id:
            meta = norm_lookup.get(lookup_id)
            if meta:
                payload.mapped_norm_source_reference = meta.get("source_reference")
                payload.mapped_norm_source_excerpt = meta.get("source_excerpt")
        items.append(payload)
    return OpenWorldCandidateList(total=total, items=items)


@router.post("/{candidate_id}/accept", response_model=OpenWorldCandidateRead)
def accept_open_world_candidate(
    candidate_id: uuid.UUID,
    payload: OpenWorldCandidateAccept | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_teacher),
) -> OpenWorldCandidateRead:
    candidate = db.get(OpenWorldCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Open-world candidate not found")
    ensure_run_access(db, candidate.review_run_id, current_user)
    if candidate.status == "accepted":
        raise HTTPException(status_code=400, detail="Candidate already accepted")
    root_dir = Path(__file__).resolve().parents[4]
    llm_norms_path = root_dir / "make_llm_norm.yaml"
    norm_id = (payload.norm_id if payload and payload.norm_id else "").strip() or _generate_make_llm_norm_id(
        llm_norms_path
    )
    title = (payload.title if payload and payload.title else candidate.title or "").strip()
    section = (payload.section if payload and payload.section else candidate.section or "Прочее").strip()
    norm_text = (
        payload.norm_text
        if payload and payload.norm_text
        else candidate.norm_text or candidate.description or ""
    ).strip()
    scope = (payload.scope if payload and payload.scope else "любой модуль").strip()
    severity = (candidate.severity or "major").strip().lower() or "major"
    if not title or not norm_text:
        raise HTTPException(status_code=400, detail="title and norm_text are required")
    try:
        append_norm_to_yaml_file(
            norm_id=norm_id,
            title=title,
            norm_text=norm_text,
            section=section,
            scope=scope,
            default_severity=severity,
            file_name="make_llm_norm.yaml",
            source_reference="LLM open-world",
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    candidate.status = "accepted"
    candidate.accepted_norm_id = norm_id
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    payload_model = OpenWorldCandidateRead.model_validate(candidate)
    norm_lookup = build_norm_lookup(db, {candidate.accepted_norm_id} if candidate.accepted_norm_id else set())
    if candidate.accepted_norm_id and candidate.accepted_norm_id in norm_lookup:
        meta = norm_lookup[candidate.accepted_norm_id]
        payload_model.mapped_norm_source_reference = meta.get("source_reference")
        payload_model.mapped_norm_source_excerpt = meta.get("source_excerpt")
    return payload_model


def _generate_make_llm_norm_id(path: Path) -> str:
    entries = load_custom_norms(path)
    max_idx = 0
    for entry in entries:
        norm_id = str(entry.get("norm_id") or "")
        if not norm_id.startswith("MAKE_LLM_"):
            continue
        suffix = norm_id.removeprefix("MAKE_LLM_")
        if suffix.isdigit():
            max_idx = max(max_idx, int(suffix))
    return f"MAKE_LLM_{max_idx + 1:03d}"
