"""
End-to-end check that create_lead/update_lead_status are manager/admin-only
over the authenticated MCP HTTP/SSE transport (/mcp/sse) -- unlike
tests/test_mcp_rbac.py, which only exercises require_role() in isolation,
this drives a real MCP client against a running server.

Requires:
  * The app running and reachable (default http://localhost:8000/mcp/sse).
  * Two existing advisor accounts: one with role='advisor', one with
    role='manager' or 'admin'. Create/promote them first, e.g.:

      curl -s -X POST http://localhost:8000/api/v1/advisors -H "Content-Type: application/json" \\
        -d '{"name":"Advisor","email":"advisor@example.com","phone":"9000000001","password":"testpass123"}'
      psql "$SYNC_DATABASE_URL" -c "UPDATE advisors SET role='manager' WHERE email='...';"

Usage:
    DATABASE_URL=<async-url> python scripts/test_role_e2e.py \\
        --advisor-email advisor@example.com --manager-email manager@example.com
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from app.db.postgres import AsyncSessionLocal
from app.models.advisor import Advisor
from app.models.client import Client  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.interaction import Interaction  # noqa: F401
from app.models.email_log import EmailLog  # noqa: F401
from app.models.whatsapp_log import WhatsAppLog  # noqa: F401
from app.core.security import create_mcp_token

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def ok(name: str, detail: str = ""):
    results.append((name, True, detail))
    print(f"  {PASS}  {name}" + (f"  ->  {detail}" if detail else ""))


def fail(name: str, detail: str = ""):
    results.append((name, False, detail))
    print(f"  {FAIL}  {name}  ->  {detail}")


async def _lookup(email: str) -> Advisor:
    async with AsyncSessionLocal() as db:
        advisor = (
            await db.execute(select(Advisor).where(Advisor.email == email))
        ).scalar_one_or_none()
        if not advisor:
            print(f"No advisor found with email {email}")
            sys.exit(1)
        return advisor


async def _call(url: str, token: str, tool: str, args: dict) -> str:
    async with sse_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            r = await session.call_tool(tool, args)
            return r.content[0].text if r.content else ""


async def main(url: str, advisor_email: str, manager_email: str):
    advisor = await _lookup(advisor_email)
    manager = await _lookup(manager_email)

    print(f"advisor: {advisor.email} (role={advisor.role})")
    print(f"manager: {manager.email} (role={manager.role})")
    if advisor.role == "advisor" and manager.role in ("manager", "admin"):
        pass
    else:
        print(
            "\nWarning: expected --advisor-email to have role='advisor' and "
            "--manager-email to have role in ('manager','admin') -- results below "
            "may not mean what you think."
        )

    advisor_token = create_mcp_token(advisor.id)
    manager_token = create_mcp_token(manager.id)

    print(f"\n=== {url} ===\n")

    print("-- plain advisor: create_lead should be forbidden --")
    result = await _call(url, advisor_token, "create_lead", {
        "advisor_id": advisor.id, "name": "role-e2e-should-not-persist",
    })
    if "forbidden" in result.lower():
        ok("advisor create_lead blocked", result)
    else:
        fail("advisor create_lead blocked", f"expected forbidden, got: {result[:120]}")

    print("\n-- plain advisor: list_leads (unrestricted tool) should still work --")
    result = await _call(url, advisor_token, "list_leads", {"advisor_id": advisor.id})
    if result.startswith("["):
        ok("advisor list_leads unaffected", result[:80])
    else:
        fail("advisor list_leads unaffected", f"unexpected: {result[:120]}")

    print("\n-- manager: create_lead should succeed --")
    result = await _call(url, manager_token, "create_lead", {
        "advisor_id": advisor.id, "name": "role-e2e-test-lead",
    })
    created_id = None
    if '"id"' in result and "error" not in result.lower():
        ok("manager create_lead succeeds", result[:120])
        import json
        created_id = json.loads(result).get("id")
    else:
        fail("manager create_lead succeeds", f"unexpected: {result[:120]}")

    if created_id:
        print("\n-- manager: update_lead_status should succeed --")
        result = await _call(url, manager_token, "update_lead_status", {
            "client_id": created_id, "status": "contacted",
        })
        if '"status": "contacted"' in result or '"status":"contacted"' in result:
            ok("manager update_lead_status succeeds", result[:120])
        else:
            fail("manager update_lead_status succeeds", f"unexpected: {result[:120]}")

        print("\n-- cleanup: deleting the test lead this script created --")
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(Client).where(Client.id == created_id))).scalar_one_or_none()
            if row:
                await db.delete(row)
                await db.commit()
                print(f"  deleted client {created_id}")

    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    print(f"\n{'='*50}\nResult: {passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/mcp/sse")
    parser.add_argument("--advisor-email", required=True, help="account with role='advisor'")
    parser.add_argument("--manager-email", required=True, help="account with role='manager' or 'admin'")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.advisor_email, args.manager_email))
