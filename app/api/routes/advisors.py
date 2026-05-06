from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.postgres import get_db
from app.models.advisor import Advisor

router = APIRouter(prefix="/api/v1", tags=["advisors"])


@router.get("/advisors")
async def list_advisors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Advisor).order_by(Advisor.created_at))
    return result.scalars().all()
