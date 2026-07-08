"""
One-off CLI to set/reset an advisor's password directly in the DB.
Needed for advisor rows created before password auth existed (password_hash is NULL).

Run from project root: python scripts/set_advisor_password.py <email> <new_password>
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal
from app.core.security import hash_password
from app.models.advisor import Advisor


async def main(email: str, password: str):
    async with AsyncSessionLocal() as db:
        advisor = (
            await db.execute(select(Advisor).where(Advisor.email == email))
        ).scalar_one_or_none()
        if not advisor:
            print(f"No advisor found with email {email}")
            return
        advisor.password_hash = hash_password(password)
        await db.commit()
        print(f"Password set for {advisor.name} <{advisor.email}>")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/set_advisor_password.py <email> <new_password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
