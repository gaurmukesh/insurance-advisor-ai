"""
One-off backfill: creates a PolicyProductLink row for every existing Policy
that predates the product-KG feature (new policies get linked automatically
at creation time, see app/api/routes/clients.py::create_policy).

Idempotent -- skips any Policy that already has a link.
Run from project root: python scripts/link_policies_to_products.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal, init_db
from app.core.knowledge_graph import link_policy_to_product
from app.models.policy import Policy
from app.models.product import PolicyProductLink
import app.models.client  # noqa: F401 -- registers FK target before create_all


async def main():
    await init_db()

    async with AsyncSessionLocal() as db:
        already_linked = {row[0] for row in (await db.execute(
            select(PolicyProductLink.policy_id)
        )).all()}

        policies = (await db.execute(select(Policy))).scalars().all()
        pending = [p for p in policies if p.id not in already_linked]

        print(f"{len(policies)} total policies, {len(pending)} without a link")

        matched, unmatched = 0, 0
        for policy in pending:
            link = await link_policy_to_product(db, policy)
            if link.match_method == "exact":
                matched += 1
            else:
                unmatched += 1

        await db.commit()
        print(f"Linked {matched} to a product, {unmatched} left unmatched")


if __name__ == "__main__":
    asyncio.run(main())
