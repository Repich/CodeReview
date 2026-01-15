from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.models.company import Company
from backend.app.models.user import UserAccount
from backend.app.schemas.companies import CompanyCreate, CompanyRead

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyRead])
def list_companies(
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    name: str | None = Query(default=None),
) -> list[Company]:
    query = db.query(Company).order_by(Company.name.asc())
    if name:
        query = query.filter(Company.name.ilike(f"%{name}%"))
    return query.offset(offset).limit(limit).all()


@router.post("", response_model=CompanyRead, status_code=201)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> Company:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    existing = db.query(Company).filter(func.lower(Company.name) == name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company already exists")
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
