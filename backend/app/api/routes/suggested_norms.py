from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_current_teacher, get_db
from backend.app.models import SuggestedNorm, SuggestedNormVote, UserAccount
from backend.app.models.norm import Norm
from backend.app.schemas.suggested_norms import (
    SuggestedNormCreate,
    SuggestedNormListResponse,
    SuggestedNormRead,
    SuggestedNormVoteCreate,
)
from backend.app.services.suggested_norms import (
    build_sections_list,
    call_llm_for_norm,
    _load_catalog_norms,
    append_suggested_norm_to_pattern_file,
)

router = APIRouter(prefix="/suggested-norms", tags=["suggested_norms"])


def _to_read_model(
    item: SuggestedNorm,
    current_user: UserAccount | None,
    vote_score: int,
    dup_titles: dict[str, str],
) -> SuggestedNormRead:
    user_vote = None
    if current_user:
        for vote in item.votes:
            if vote.voter_id == current_user.id:
                user_vote = vote.vote
                break
    return SuggestedNormRead(
        id=item.id,
        author_id=item.author_id,
        section=item.section,
        severity=item.severity,
        text_raw=item.text_raw,
        status=item.status,
        duplicate_of=item.duplicate_of,
        duplicate_titles={k: dup_titles.get(k) for k in (item.duplicate_of or [])},
        generated_norm_id=item.generated_norm_id,
        generated_title=item.generated_title,
        generated_section=item.generated_section,
        generated_scope=item.generated_scope,
        generated_detector_type=item.generated_detector_type,
        generated_check_type=item.generated_check_type,
        generated_severity=item.generated_severity,
        generated_version=item.generated_version,
        generated_text=item.generated_text,
        created_at=item.created_at,
        updated_at=item.updated_at,
        vote_score=vote_score,
        user_vote=user_vote,
    )


@router.get("/sections", response_model=list[str])
def list_sections(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> list[str]:
    db_norms = db.query(Norm).all()
    catalog_norms = _load_catalog_norms()
    return build_sections_list(db_norms, catalog_norms)


@router.post("", response_model=SuggestedNormRead, status_code=201)
def create_suggested_norm(
    payload: SuggestedNormCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> SuggestedNormRead:
    db_norms = db.query(Norm).all()
    catalog_norms = _load_catalog_norms()
    try:
        llm_result = call_llm_for_norm(
            user_section=payload.section,
            user_severity=payload.severity,
            user_text=payload.text,
            db_norms=db_norms,
            catalog_norms=catalog_norms,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    dup_titles = {n.norm_id: n.title for n in db.query(Norm).all()}
    norm = SuggestedNorm(
        author_id=current_user.id,
        section=payload.section,
        severity=payload.severity,
        text_raw=payload.text,
        status="rejected_duplicate" if llm_result.duplicate else "accepted_auto",
        llm_prompt=None,
        llm_response=llm_result.raw_response,
        duplicate_of=llm_result.duplicate_norm_ids or None,
        generated_norm_id=llm_result.norm_id,
        generated_title=llm_result.title,
        generated_section=llm_result.section,
        generated_scope=llm_result.scope,
        generated_detector_type=llm_result.detector_type,
        generated_check_type=llm_result.check_type,
        generated_severity=llm_result.default_severity,
        generated_version=llm_result.version,
        generated_text=llm_result.norm_text,
    )
    db.add(norm)
    db.commit()
    db.refresh(norm)
    return _to_read_model(norm, current_user, vote_score=0, dup_titles=dup_titles)


@router.get("", response_model=SuggestedNormListResponse)
def list_suggested_norms(
    status: str | None = Query(
        default=None,
        pattern="^(pending|accepted_auto|accepted_manual|rejected_duplicate|rejected_manual)$",
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> SuggestedNormListResponse:
    query = db.query(SuggestedNorm)
    if status:
        query = query.filter(SuggestedNorm.status == status)
    total = query.count()
    items = query.order_by(SuggestedNorm.created_at.desc()).offset(offset).limit(limit).all()
    dup_titles = {n.norm_id: n.title for n in db.query(Norm).all()}
    results: list[SuggestedNormRead] = []
    for item in items:
        vote_sum = db.query(func.coalesce(func.sum(SuggestedNormVote.vote), 0)).filter(
            SuggestedNormVote.norm_id == item.id
        ).scalar()
        results.append(_to_read_model(item, current_user, vote_score=vote_sum or 0, dup_titles=dup_titles))
    return SuggestedNormListResponse(items=results, total=total)


@router.post("/{norm_id}/vote", status_code=204)
def vote_suggested_norm(
    norm_id: str,
    payload: SuggestedNormVoteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> None:
    norm = db.query(SuggestedNorm).filter_by(id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Suggested norm not found")
    if payload.vote not in (-1, 1):
        raise HTTPException(status_code=400, detail="vote must be +1 or -1")
    existing = (
        db.query(SuggestedNormVote)
        .filter_by(norm_id=norm.id, voter_id=current_user.id)
        .first()
    )
    if existing:
        existing.vote = payload.vote
        db.add(existing)
    else:
        db.add(
            SuggestedNormVote(
                norm_id=norm.id,
                voter_id=current_user.id,
                vote=payload.vote,
            )
        )
    db.commit()


@router.post("/{norm_id}/accept", response_model=SuggestedNormRead)
def accept_suggested_norm(
    norm_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> SuggestedNormRead:
    norm = db.query(SuggestedNorm).filter_by(id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Suggested norm not found")
    if norm.status in {"accepted_auto", "accepted_manual"}:
        raise HTTPException(status_code=400, detail="Suggested norm already accepted")
    if norm.status == "rejected_duplicate" or norm.duplicate_of:
        raise HTTPException(status_code=400, detail="Duplicate suggested norm cannot be accepted")
    if not norm.generated_norm_id or not norm.generated_title or not norm.generated_text:
        raise HTTPException(status_code=400, detail="Suggested norm is missing generated fields")
    try:
        append_suggested_norm_to_pattern_file(norm)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    norm.status = "accepted_manual"
    db.add(norm)
    db.commit()
    db.refresh(norm)
    vote_sum = db.query(func.coalesce(func.sum(SuggestedNormVote.vote), 0)).filter(
        SuggestedNormVote.norm_id == norm.id
    ).scalar()
    dup_titles = {n.norm_id: n.title for n in db.query(Norm).all()}
    return _to_read_model(norm, current_user, vote_score=vote_sum or 0, dup_titles=dup_titles)
