"""
Lists an advisor's MCP tokens, or revokes one by id.

Usage:
    DATABASE_URL=<async-url> python scripts/revoke_mcp_token.py --email you@example.com
    DATABASE_URL=<async-url> python scripts/revoke_mcp_token.py --revoke <token-id>
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal
from app.models.advisor import Advisor
from app.models.client import Client  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.interaction import Interaction  # noqa: F401
from app.models.email_log import EmailLog  # noqa: F401
from app.models.whatsapp_log import WhatsAppLog  # noqa: F401
from app.models.mcp_token import MCPToken  # noqa: F401
from app.mcp.tokens import list_tokens, revoke_token


async def list_for_email(email: str):
    async with AsyncSessionLocal() as db:
        advisor = (
            await db.execute(select(Advisor).where(Advisor.email == email))
        ).scalar_one_or_none()
        if not advisor:
            print(f"No advisor found with email {email}")
            sys.exit(1)

        tokens = await list_tokens(db, advisor.id)
        if not tokens:
            print(f"No tokens for {email}")
            return
        for t in tokens:
            status = "revoked" if t.revoked_at else "active"
            print(f"{t.id}  created={t.created_at}  expires={t.expires_at}  [{status}]")


async def revoke(token_id: str):
    async with AsyncSessionLocal() as db:
        ok = await revoke_token(db, token_id)
        print("Revoked." if ok else "Token not found or already revoked.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="list tokens for this advisor")
    group.add_argument("--revoke", metavar="TOKEN_ID", help="revoke a specific token by id")
    args = parser.parse_args()

    if args.email:
        asyncio.run(list_for_email(args.email))
    else:
        asyncio.run(revoke(args.revoke))
