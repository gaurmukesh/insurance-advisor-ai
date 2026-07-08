from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.api.deps import get_current_advisor
from app.db.postgres import get_db
from app.models.advisor import Advisor
from app.models.client import Client
from app.modules.pitch_handler import generate_pitch, handle_objection, COMMON_OBJECTIONS

router = APIRouter(prefix="/api/v1", tags=["pitch"])


@router.get("/pitch/common-objections")
async def get_common_objections(current: Advisor = Depends(get_current_advisor)):
    return {"objections": COMMON_OBJECTIONS}


class PitchRequest(BaseModel):
    client_id: str
    existing_policies: Optional[str] = None


class ObjectionRequest(BaseModel):
    client_id: str
    objection: str
    existing_policies: Optional[str] = None


async def _get_own_client(db: AsyncSession, client_id: str, advisor: Advisor) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or client.advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/generate-pitch")
async def generate_pitch_endpoint(
    data: PitchRequest,
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

    pitch = await generate_pitch(profile)
    return {"client_id": client.id, "client_name": client.name, "pitch": pitch}


@router.post("/handle-objection")
async def handle_objection_endpoint(
    data: ObjectionRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = await _get_own_client(db, data.client_id, current)

    profile = {
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "goals": client.goals,
        "existing_policies": data.existing_policies or client.existing_coverage or "None",
        "employment_type": client.employment_type or "Not specified",
        "health_conditions": client.health_conditions or "None",
        "liabilities_emi": client.liabilities_emi or 0,
    }

    response = await handle_objection(data.objection, profile)
    return {"client_id": client.id, "objection": data.objection, "response": response}
