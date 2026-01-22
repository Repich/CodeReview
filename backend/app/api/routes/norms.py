from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_teacher, get_db
from backend.app.models.norm import Norm
from backend.app.schemas.norms import NormCatalogEntry, NormCreate, NormRead, NormUpdate
from backend.app.services.norms import (
    filter_norm_catalog_entries,
    load_custom_norms,
    load_norm_catalog_entries,
    save_custom_norms,
)

router = APIRouter(prefix="/norms", tags=["norms"])


@router.get("", response_model=list[NormRead])
def list_norms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(get_current_teacher),
    db: Session = Depends(get_db),
) -> list[NormRead]:
    return db.query(Norm).offset(skip).limit(limit).all()


def _create_norm(payload: NormCreate, db: Session) -> Norm:
    norm = Norm(**payload.model_dump())
    db.add(norm)
    db.commit()
    db.refresh(norm)
    return norm


@router.get("/catalog", response_model=list[NormCatalogEntry])
def list_norm_catalog(
    source: str = Query("static", pattern="^(static|llm)$"),
    query: str | None = Query(default=None),
    limit: int = Query(200, ge=1, le=2000),
    current_user=Depends(get_current_teacher),
) -> list[NormCatalogEntry]:
    root_dir = Path(__file__).resolve().parents[4]
    if source == "llm":
        paths = [root_dir / "critical_norms.yaml"]
    else:
        paths = [root_dir / "norms.yaml", root_dir / "custom_norms.yaml", root_dir / "pattern_1С.yaml"]
    entries = []
    seen_ids: set[str] = set()
    for path in paths:
        for entry in load_norm_catalog_entries(path):
            norm_id = entry.get("norm_id")
            if not norm_id or norm_id in seen_ids:
                continue
            seen_ids.add(norm_id)
            entries.append(entry)
    filtered = filter_norm_catalog_entries(entries, query, limit)
    return [NormCatalogEntry(**entry) for entry in filtered]


@router.get("/custom", response_model=list[NormCatalogEntry])
def list_custom_norms(
    current_user=Depends(get_current_teacher),
) -> list[NormCatalogEntry]:
    root_dir = Path(__file__).resolve().parents[4]
    path = root_dir / "custom_norms.yaml"
    entries = load_custom_norms(path)
    return [NormCatalogEntry(**entry) for entry in entries]


@router.delete("/custom/{norm_id}", status_code=204)
def delete_custom_norm(
    norm_id: str,
    current_user=Depends(get_current_teacher),
) -> None:
    root_dir = Path(__file__).resolve().parents[4]
    path = root_dir / "custom_norms.yaml"
    entries = load_custom_norms(path)
    filtered = [entry for entry in entries if entry.get("norm_id") != norm_id]
    if len(filtered) == len(entries):
        raise HTTPException(status_code=404, detail="Custom norm not found")
    save_custom_norms(path, filtered)


@router.post("", response_model=NormRead, status_code=201)
def create_norm(
    payload: NormCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> Norm:
    return _create_norm(payload, db)


@router.get("/{norm_id}", response_model=NormRead)
def get_norm(
    norm_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> Norm:
    norm = db.query(Norm).filter_by(norm_id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")
    return norm


@router.patch("/{norm_id}", response_model=NormRead)
def update_norm(
    norm_id: str,
    payload: NormUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
) -> Norm:
    norm = db.query(Norm).filter_by(norm_id=norm_id).first()
    if not norm:
        raise HTTPException(status_code=404, detail="Norm not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(norm, field, value)
    db.add(norm)
    db.commit()
    db.refresh(norm)
    return norm
