"""
Mints a long-lived JWT for the mcp-remote Claude Desktop bridge to /mcp/sse.

Run this against whichever DATABASE_URL points at the Postgres holding the
advisor account -- PROD_DATABASE_URL for the deployed Lightsail service (what
Claude Desktop's mcp-remote config actually talks to), or the local .env for
a dev instance.

Usage:
    DATABASE_URL=<prod-or-local-async-url> python scripts/mint_mcp_token.py --email you@example.com
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
from app.core.security import create_mcp_token, MCP_TOKEN_EXPIRE_DAYS


async def main(email: str):
    async with AsyncSessionLocal() as db:
        advisor = (
            await db.execute(select(Advisor).where(Advisor.email == email))
        ).scalar_one_or_none()
        if not advisor:
            print(f"No advisor found with email {email}")
            sys.exit(1)

        token = create_mcp_token(advisor.id)
        print(f"Advisor: {advisor.name} ({advisor.id}), role={advisor.role}")
        print(f"Valid for {MCP_TOKEN_EXPIRE_DAYS} days.\n")
        print(token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.email))
