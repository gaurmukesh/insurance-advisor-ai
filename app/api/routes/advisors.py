from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
from app.db.postgres import get_db
from app.models.advisor import Advisor

router = APIRouter(prefix="/api/v1", tags=["advisors"])


class AdvisorCreate(BaseModel):
    name: str
    email: str
    phone: str
    license_no: Optional[str] = None


@router.get("/advisors")
async def list_advisors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Advisor).order_by(Advisor.created_at))
    return result.scalars().all()


@router.post("/advisors", status_code=201)
async def create_advisor(data: AdvisorCreate, db: AsyncSession = Depends(get_db)):
    advisor = Advisor(**data.model_dump())
    db.add(advisor)
    try:
        await db.commit()
        await db.refresh(advisor)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Advisor email already exists")
    return advisor
