from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.mcp.tokens import mint_token, resolve_advisor_id, revoke_token, list_tokens
from app.models.mcp_token import MCPToken


@pytest.mark.asyncio
async def test_mint_then_resolve_roundtrip(db_session, advisor):
    token = await mint_token(db_session, advisor.id)
    assert token.startswith("mcp_")

    resolved = await resolve_advisor_id(db_session, token)
    assert resolved == advisor.id


@pytest.mark.asyncio
async def test_resolve_rejects_garbage_token(db_session, advisor):
    assert await resolve_advisor_id(db_session, "not-a-real-token") is None
    assert await resolve_advisor_id(db_session, "mcp_" + "x" * 40) is None


@pytest.mark.asyncio
async def test_resolve_rejects_revoked_token(db_session, advisor):
    token = await mint_token(db_session, advisor.id)
    row = (await db_session.execute(
        select(MCPToken).where(MCPToken.advisor_id == advisor.id)
    )).scalar_one()

    assert await revoke_token(db_session, row.id) is True
    assert await resolve_advisor_id(db_session, token) is None
    # revoking twice is a no-op, not an error
    assert await revoke_token(db_session, row.id) is False


@pytest.mark.asyncio
async def test_resolve_rejects_expired_token(db_session, advisor):
    token = await mint_token(db_session, advisor.id)
    row = (await db_session.execute(
        select(MCPToken).where(MCPToken.advisor_id == advisor.id)
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    assert await resolve_advisor_id(db_session, token) is None


@pytest.mark.asyncio
async def test_list_tokens_orders_newest_first(db_session, advisor):
    await mint_token(db_session, advisor.id)
    await mint_token(db_session, advisor.id)

    tokens = await list_tokens(db_session, advisor.id)
    assert len(tokens) == 2
    assert tokens[0].created_at >= tokens[1].created_at
