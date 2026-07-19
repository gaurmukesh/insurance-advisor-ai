import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_token import MCPToken

MCP_TOKEN_EXPIRE_DAYS = 365
TOKEN_PREFIX = "mcp_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def mint_token(db: AsyncSession, advisor_id: str) -> str:
    """Create a new opaque token for advisor_id and return the raw value.
    Only the SHA-256 hash is persisted -- this is the one time the raw
    token is ever available; it can't be recovered from the DB afterward."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = MCPToken(
        advisor_id=advisor_id,
        token_hash=_hash(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=MCP_TOKEN_EXPIRE_DAYS),
    )
    db.add(row)
    await db.commit()
    return token


async def resolve_advisor_id(db: AsyncSession, token: str) -> str | None:
    """Returns the advisor_id for a valid, unexpired, unrevoked token, else None."""
    if not token.startswith(TOKEN_PREFIX):
        return None
    row = (
        await db.execute(select(MCPToken).where(MCPToken.token_hash == _hash(token)))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at < datetime.now(timezone.utc):
        return None
    return row.advisor_id


async def list_tokens(db: AsyncSession, advisor_id: str) -> list[MCPToken]:
    rows = (
        await db.execute(
            select(MCPToken).where(MCPToken.advisor_id == advisor_id).order_by(MCPToken.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def revoke_token(db: AsyncSession, token_id: str) -> bool:
    row = (await db.execute(select(MCPToken).where(MCPToken.id == token_id))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return True
