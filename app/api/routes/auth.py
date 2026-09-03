from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_advisor
from app.core.rate_limit import limiter
from app.core.security import create_access_token, verify_password
from app.db.postgres import get_db
from app.models.advisor import Advisor

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    advisor: dict


def _advisor_dict(advisor: Advisor) -> dict:
    return {
        "id": advisor.id,
        "name": advisor.name,
        "email": advisor.email,
        "phone": advisor.phone,
        "license_no": advisor.license_no,
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    advisor = (
        await db.execute(select(Advisor).where(Advisor.email == data.email))
    ).scalar_one_or_none()

    if not advisor or not advisor.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(data.password, advisor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(advisor.id)
    return {"access_token": token, "advisor": _advisor_dict(advisor)}


@router.get("/me")
async def me(current_advisor: Advisor = Depends(get_current_advisor)):
    return _advisor_dict(current_advisor)
