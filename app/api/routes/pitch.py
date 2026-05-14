from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.db.postgres import get_db
from app.models.client import Client
from app.modules.pitch_handler import generate_pitch, handle_objection, COMMON_OBJECTIONS

router = APIRouter(prefix="/api/v1", tags=["pitch"])


@router.get("/pitch/common-objections")
async def get_common_objections():
    return {"objections": COMMON_OBJECTIONS}


class PitchRequest(BaseModel):
    client_id: str
    existing_policies: Optional[str] = None


class ObjectionRequest(BaseModel):
    client_id: str
    objection: str
    existing_policies: Optional[str] = None


@router.post("/generate-pitch")
async def generate_pitch_endpoint(data: PitchRequest, db: AsyncSession = Depends(get_db)):
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

    pitch = await generate_pitch(profile)
    return {"client_id": client.id, "client_name": client.name, "pitch": pitch}


@router.post("/handle-objection")
async def handle_objection_endpoint(data: ObjectionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = {
        "age": client.age,
        "income": client.income,
        "family_size": client.family_size,
        "goals": client.goals,
        "existing_policies": data.existing_policies or "None",
    }

    response = await handle_objection(data.objection, profile)
    return {"client_id": client.id, "objection": data.objection, "response": response}
