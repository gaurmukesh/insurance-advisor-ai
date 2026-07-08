import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.advisor import Advisor

_bearer = HTTPBearer(auto_error=False)


async def get_current_advisor(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Advisor:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        advisor_id = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    advisor = (
        await db.execute(select(Advisor).where(Advisor.id == advisor_id))
    ).scalar_one_or_none()
    if not advisor:
        raise HTTPException(status_code=401, detail="Advisor not found")
    return advisor
