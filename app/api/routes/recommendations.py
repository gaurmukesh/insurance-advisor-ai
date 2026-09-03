from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.deps import get_current_advisor
from app.core.knowledge_graph import fetch_kg_facts
from app.db.postgres import get_db
from app.models.advisor import Advisor
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


async def _get_own_client(db: AsyncSession, client_id: str, advisor: Advisor) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or client.advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/analyze-client")
async def analyze_client(
    data: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = await _get_own_client(db, data.client_id, current)

    profile = {
        "name": client.name,
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "risk_appetite": client.risk_appetite,
        "goals": client.goals,
        "existing_policies": data.existing_policies or client.existing_coverage or "None",
        "existing_coverage": client.existing_coverage or "None",
        "liabilities_emi": client.liabilities_emi or 0,
        "employment_type": client.employment_type or "Not specified",
        "health_conditions": client.health_conditions or "None",
        "dependents_detail": client.dependents_detail or "None",
        "city_tier": client.city_tier or "Not specified",
    }

    kg_facts = await fetch_kg_facts(db, client.id, profile)
    analysis = await analyze_client_needs(db, profile, kg_facts)
    return {"client_id": client.id, "client_name": client.name, "analysis": analysis}


@router.post("/recommend-products")
async def recommend(
    data: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = await _get_own_client(db, data.client_id, current)

    profile = {
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "risk_appetite": client.risk_appetite,
        "goals": client.goals,
        "existing_policies": data.existing_policies or client.existing_coverage or "None",
        "existing_coverage": client.existing_coverage or "None",
        "liabilities_emi": client.liabilities_emi or 0,
        "employment_type": client.employment_type or "Not specified",
        "health_conditions": client.health_conditions or "None",
        "dependents_detail": client.dependents_detail or "None",
        "city_tier": client.city_tier or "Not specified",
    }

    kg_facts = await fetch_kg_facts(db, client.id, profile)
    recommendations = await recommend_products(db, profile, data.need_analysis, kg_facts)
    return {"client_id": client.id, "client_name": client.name, "recommendations": recommendations}
