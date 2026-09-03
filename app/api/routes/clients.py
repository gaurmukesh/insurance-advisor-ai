from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date, timedelta
from typing import Optional
from app.api.deps import get_current_advisor
from app.db.postgres import get_db
from app.core.knowledge_graph import link_policy_to_product
from app.models.advisor import Advisor
from app.models.client import Client
from app.models.policy import Policy

router = APIRouter(prefix="/api/v1", tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    age: int | None = None
    income: float | None = None
    family_size: int | None = None
    risk_appetite: str | None = None
    goals: str | None = None
    notes: str | None = None
    existing_coverage: str | None = None
    liabilities_emi: float | None = None
    employment_type: str | None = None
    health_conditions: str | None = None
    dependents_detail: str | None = None
    city_tier: str | None = None


class ClientUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    goals: str | None = None
    existing_coverage: str | None = None
    liabilities_emi: float | None = None
    employment_type: str | None = None
    health_conditions: str | None = None
    dependents_detail: str | None = None
    city_tier: str | None = None


async def _get_own_client(db: AsyncSession, client_id: str, advisor: Advisor) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or client.advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/leads")
async def create_lead(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = Client(advisor_id=current.id, **data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/leads")
async def list_leads(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    query = select(Client).where(Client.advisor_id == current.id)
    if status:
        query = query.where(Client.status == status)
    query = query.order_by(Client.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/leads/{client_id}")
async def get_lead(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    return await _get_own_client(db, client_id, current)


@router.put("/leads/{client_id}")
async def update_lead(
    client_id: str,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = await _get_own_client(db, client_id, current)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(client, field, value)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/renewals/upcoming")
async def upcoming_renewals(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    today = date.today()
    until = today + timedelta(days=days)

    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Client.advisor_id == current.id)
        .where(Policy.next_due_date >= today)
        .where(Policy.next_due_date <= until)
        .order_by(Policy.next_due_date)
    )
    rows = result.all()
    return [
        {
            "policy_id": policy.id,
            "policy_no": policy.policy_no,
            "product_name": policy.product_name,
            "insurer_name": policy.insurer_name,
            "premium_amount": policy.premium_amount,
            "next_due_date": str(policy.next_due_date),
            "client_id": client.id,
            "client_name": client.name,
            "client_email": client.email,
            "client_phone": client.phone,
        }
        for policy, client in rows
    ]


class PolicyCreate(BaseModel):
    client_id: str
    insurer_name: str
    product_name: str
    policy_no: str
    policy_type: str
    premium_amount: float
    sum_assured: Optional[float] = None
    next_due_date: Optional[date] = None
    expiry_date: Optional[date] = None


@router.post("/policies", status_code=201)
async def create_policy(
    data: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    await _get_own_client(db, data.client_id, current)
    policy = Policy(**data.model_dump())
    db.add(policy)
    await db.flush()
    await link_policy_to_product(db, policy)
    await db.commit()
    await db.refresh(policy)
    return policy
