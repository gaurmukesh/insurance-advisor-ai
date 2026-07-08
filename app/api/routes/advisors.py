from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
from app.api.deps import get_current_advisor
from app.core.security import hash_password
from app.db.postgres import get_db
from app.models.advisor import Advisor

router = APIRouter(prefix="/api/v1", tags=["advisors"])


class AdvisorCreate(BaseModel):
    name: str
    email: str
    phone: str
    password: str
    license_no: Optional[str] = None


class AdvisorOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str
    license_no: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/advisors", response_model=list[AdvisorOut])
async def list_advisors(
    db: AsyncSession = Depends(get_db),
    _current: Advisor = Depends(get_current_advisor),
):
    result = await db.execute(select(Advisor).order_by(Advisor.created_at))
    return result.scalars().all()


@router.post("/advisors", status_code=201, response_model=AdvisorOut)
async def create_advisor(data: AdvisorCreate, db: AsyncSession = Depends(get_db)):
    """Public advisor self-registration — no auth required (nothing to authenticate
    against before an account exists)."""
    advisor = Advisor(
        name=data.name,
        email=data.email,
        phone=data.phone,
        license_no=data.license_no,
        password_hash=hash_password(data.password),
    )
    db.add(advisor)
    try:
        await db.commit()
        await db.refresh(advisor)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Advisor email already exists")
    return advisor
