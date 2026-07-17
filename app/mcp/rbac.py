import functools
import json

from app.mcp.auth_middleware import current_advisor


def require_role(*roles: str):
    """Gate an MCP tool to callers whose Advisor.role is one of `roles`.

    Must sit *between* @mcp.tool() and the function -- i.e. applied first --
    so FastMCP registers this wrapper as the tool entrypoint:

        @mcp.tool()
        @require_role("advisor", "manager", "admin")
        async def some_tool(...): ...

    functools.wraps preserves the original signature via __wrapped__, which
    FastMCP's schema introspection follows, so the tool's input schema is
    unaffected by this wrapper.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            advisor = current_advisor.get()
            if advisor is None or advisor.role not in roles:
                return json.dumps({"error": "forbidden"})
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def scoped_advisor_id(requested: str) -> str:
    """Plain advisors can only ever act as themselves; manager/admin may pass
    another advisor_id to see cross-advisor data. Only call this inside a
    require_role-gated tool, where current_advisor is guaranteed set."""
    advisor = current_advisor.get()
    if advisor.role == "advisor":
        return advisor.id
    return requested


def owns_client(client) -> bool:
    """True if the current caller may act on this client: it's their own
    lead, or they hold a cross-advisor role (manager/admin)."""
    advisor = current_advisor.get()
    return advisor.role in ("manager", "admin") or client.advisor_id == advisor.id
