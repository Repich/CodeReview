from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.api.utils import ensure_run_access
from backend.app.models.feedback import Feedback
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.models.enums import UserRole
from backend.app.schemas.feedback import FeedbackCreate, FeedbackList, FeedbackRead

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("", response_model=FeedbackList)
def list_feedback(
    finding_id: uuid.UUID | None = Query(default=None),
    review_run_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> FeedbackList:
    query = db.query(Feedback).join(ReviewRun, ReviewRun.id == Feedback.review_run_id)
    if finding_id:
        query = query.filter(Feedback.finding_id == finding_id)
    if review_run_id:
        query = query.filter(Feedback.review_run_id == review_run_id)
    if current_user.role != UserRole.ADMIN:
        if current_user.company_id:
            query = query.join(UserAccount, UserAccount.id == ReviewRun.user_id).filter(
                UserAccount.company_id == current_user.company_id
            )
        else:
            query = query.filter(ReviewRun.user_id == current_user.id)
    items = query.order_by(Feedback.created_at.desc()).all()
    return FeedbackList(total=len(items), items=items)


@router.post("", response_model=FeedbackRead, status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> Feedback:
    ensure_run_access(db, payload.review_run_id, current_user, require_owner=True)
    feedback = Feedback(**payload.model_dump())
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/{feedback_id}", response_model=FeedbackRead)
def get_feedback(
    feedback_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    ensure_run_access(db, feedback.review_run_id, current_user)
    return feedback
