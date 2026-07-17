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
            # None means no auth middleware ran at all -- i.e. this call came
            # in over the stdio transport (Claude Desktop, local dev), which
            # has no HTTP request to authenticate and is treated as a trusted
            # local process, same as before roles existed. Over HTTP/SSE,
            # MCPAuthMiddleware always either sets a real Advisor or
            # short-circuits with 401 before a tool is ever reached, so None
            # can only mean stdio here -- it can't mean "HTTP request with no
            # token."
            if advisor is not None and advisor.role not in roles:
                return json.dumps({"error": "forbidden"})
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def scoped_advisor_id(requested: str) -> str:
    """Plain advisors can only ever act as themselves; manager/admin may pass
    another advisor_id to see cross-advisor data. Over stdio (no authenticated
    advisor in context) this is a no-op -- the caller-supplied ID passes
    through unchanged, matching pre-RBAC behavior."""
    advisor = current_advisor.get()
    if advisor is not None and advisor.role == "advisor":
        return advisor.id
    return requested


def owns_client(client) -> bool:
    """True if the current caller may act on this client: it's their own
    lead, they hold a cross-advisor role (manager/admin), or there's no
    authenticated advisor in context at all (stdio transport)."""
    advisor = current_advisor.get()
    if advisor is None:
        return True
    return advisor.role in ("manager", "admin") or client.advisor_id == advisor.id
