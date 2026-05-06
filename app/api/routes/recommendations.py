from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.postgres import get_db
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs
from app.modules.product_recommender import recommend_products

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


class AnalyzeRequest(BaseModel):
    client_id: str
    existing_policies: str | None = None


class RecommendRequest(BaseModel):
    client_id: str
    need_analysis: str
    existing_policies: str | None = None


@router.post("/analyze-client")
async def analyze_client(data: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = {
        "name": client.name,
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "risk_appetite": client.risk_appetite,
        "goals": client.goals,
        "existing_policies": data.existing_policies or "None",
    }

    analysis = await analyze_client_needs(db, profile)
    return {"client_id": client.id, "client_name": client.name, "analysis": analysis}


@router.post("/recommend-products")
async def recommend(data: RecommendRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = {
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "risk_appetite": client.risk_appetite,
        "goals": client.goals,
        "existing_policies": data.existing_policies or "None",
    }

    recommendations = await recommend_products(db, profile, data.need_analysis)
    return {"client_id": client.id, "client_name": client.name, "recommendations": recommendations}
