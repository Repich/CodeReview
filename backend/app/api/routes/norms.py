from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.models.norm import Norm
from backend.app.schemas.norms import NormCreate, NormRead, NormUpdate

router = APIRouter(prefix="/norms", tags=["norms"])


@router.get("", response_model=list[NormRead])
def list_norms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NormRead]:
    return db.query(Norm).offset(skip).limit(limit).all()


@router.post("", response_model=NormRead, status_code=201)
def create_norm(payload: NormCreate, db: Session = Depends(get_db)) -> Norm:
    norm = Norm(**payload.model_dump())
    db.add(norm)
    db.commit()
    db.refresh(norm)
    return norm


@router.get("/{norm_id}", response_model=NormRead)
def get_norm(norm_id: str, db: Session = Depends(get_db)) -> Norm:
    norm = db.query(Norm).filter_by(norm_id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")
    return norm


@router.patch("/{norm_id}", response_model=NormRead)
def update_norm(norm_id: str, payload: NormUpdate, db: Session = Depends(get_db)) -> Norm:
    norm = db.query(Norm).filter_by(norm_id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(norm, field, value)
    db.add(norm)
    db.commit()
    db.refresh(norm)
    return norm
