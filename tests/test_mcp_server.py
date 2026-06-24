"""
Test MCP server without Claude Desktop.
Uses the official MCP Python client over stdio — same protocol Claude Desktop uses.

Run:
    python tests/test_mcp_server.py
"""
import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# ── server launch config ───────────────────────────────────────────
SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp.server"],
    env=None,  # inherits .env via python-dotenv in app startup
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


SKIP = "\033[33mSKIP\033[0m"
DB_ERRORS = ("connect call fa", "connection refused", "multiple exceptions", "errno 61")


def ok(name: str, detail: str = ""):
    results.append((name, True, detail))
    print(f"  {PASS}  {name}" + (f"  →  {detail}" if detail else ""))


def skip(name: str, detail: str = ""):
    results.append((name, None, detail))
    print(f"  {SKIP}  {name}  →  {detail}")


def fail(name: str, detail: str = ""):
    results.append((name, False, detail))
    print(f"  {FAIL}  {name}  →  {detail}")


def is_db_error(text: str) -> bool:
    lower = text.lower()
    return any(e in lower for e in DB_ERRORS)


async def main():
    print("\n=== MCP Server Test (stdio transport) ===\n")

    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 1. List tools ──────────────────────────────────────
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}
            expected = {
                "list_leads", "get_client", "create_lead", "update_lead_status",
                "analyze_needs", "get_recommendations", "generate_sales_pitch",
                "handle_client_objection", "search_policy_docs", "get_upcoming_renewals",
            }
            print("── Tool registration ─────────────────────────────────")
            for name in sorted(expected):
                if name in tool_names:
                    ok(name)
                else:
                    fail(name, "not registered")

            # ── 2. Call tools that don't need a real DB row ────────
            print("\n── Tool calls (no DB data needed) ────────────────────")

            # get_client with a fake ID — should return error JSON, not crash
            r = await session.call_tool("get_client", {"client_id": "nonexistent-id"})
            content = r.content[0].text if r.content else ""
            if "error" in content.lower() or "not found" in content.lower():
                ok("get_client (unknown id)", "returns error JSON gracefully")
            else:
                fail("get_client (unknown id)", f"unexpected: {content[:80]}")

            # list_leads with a fake advisor ID — should return empty list, not crash
            r = await session.call_tool("list_leads", {"advisor_id": "test-advisor-000"})
            content = r.content[0].text if r.content else ""
            if content.startswith("["):
                ok("list_leads (empty advisor)", f"returned JSON array: {content[:40]}")
            elif is_db_error(content):
                skip("list_leads (empty advisor)", "DB not reachable — start PostgreSQL to test")
            else:
                fail("list_leads (empty advisor)", f"unexpected: {content[:80]}")

            # get_upcoming_renewals — should return empty list
            r = await session.call_tool("get_upcoming_renewals", {"advisor_id": "test-advisor-000"})
            content = r.content[0].text if r.content else ""
            if content.startswith("["):
                ok("get_upcoming_renewals (empty)", "returned JSON array")
            elif is_db_error(content):
                skip("get_upcoming_renewals (empty)", "DB not reachable — start PostgreSQL to test")
            else:
                fail("get_upcoming_renewals (empty)", f"unexpected: {content[:80]}")

            # search_policy_docs — should return gracefully when no docs indexed
            r = await session.call_tool("search_policy_docs", {"query": "term life insurance coverage"})
            content = r.content[0].text if r.content else ""
            if content:
                ok("search_policy_docs", f"{content[:60]}")
            else:
                fail("search_policy_docs", "empty response")

            # analyze_needs with nonexistent client — should return error JSON
            r = await session.call_tool("analyze_needs", {"client_id": "nonexistent-id"})
            content = r.content[0].text if r.content else ""
            if "error" in content.lower() or "not found" in content.lower():
                ok("analyze_needs (unknown id)", "returns error JSON gracefully")
            else:
                fail("analyze_needs (unknown id)", f"unexpected: {content[:80]}")

    # ── summary ───────────────────────────────────────────────────
    passed = sum(1 for _, p, _ in results if p is True)
    failed = sum(1 for _, p, _ in results if p is False)
    skipped = sum(1 for _, p, _ in results if p is None)
    print(f"\n{'='*50}")
    print(f"Result: {passed} passed, {failed} failed, {skipped} skipped (DB offline)")
    if failed:
        print("\nFailed checks:")
        for name, p, detail in results:
            if p is False:
                print(f"  • {name}: {detail}")
    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
