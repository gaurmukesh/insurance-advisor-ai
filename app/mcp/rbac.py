import contextvars
import functools
import json

from app.mcp.auth_middleware import current_advisor
from app.mcp.policy_engine import evaluate

# Set by authorize() for the lifetime of one tool call, read by
# scoped_advisor_id/owns_client below. Defaults to "self" (most restrictive)
# so that a tool which somehow runs without the authorize() decorator fails
# closed rather than open.
_resource_scope: contextvars.ContextVar[str] = contextvars.ContextVar(
    "resource_scope", default="self"
)


def authorize(action: str):
    """Gate an MCP tool with a declarative, IAM-style policy check --
    app/mcp/policies.py's Allow/Deny statements over Action/Resource,
    evaluated by app.mcp.policy_engine.evaluate(). Replaces require_role's
    hardcoded per-tool role tuples: adding a role or changing a tool's access
    is a policy-document change, not a decorator-argument change.

    Must sit *between* @mcp.tool() and the function -- i.e. applied first --
    so FastMCP registers this wrapper as the tool entrypoint:

        @mcp.tool()
        @authorize("mcp:create_lead")
        async def create_lead(...): ...

    functools.wraps preserves the original signature via __wrapped__, which
    FastMCP's schema introspection follows, so the tool's input schema is
    unaffected by this wrapper.

    On success, sets resource_scope ("self" or "*") for the duration of the
    call so scoped_advisor_id/owns_client know whether this caller may act
    on any advisor's data or only their own -- unifying what used to be two
    separate mechanisms (the coarse role gate and the per-record ownership
    check) under one policy evaluation.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            advisor = current_advisor.get()
            # None means stdio (see current_advisor's docstring) -- treated
            # as a trusted local process, same as before the policy engine.
            role = advisor.role if advisor is not None else None
            decision = evaluate(role, action)
            if not decision.allowed:
                return json.dumps({"error": "forbidden"})

            token = _resource_scope.set(decision.resource_scope)
            try:
                return await fn(*args, **kwargs)
            finally:
                _resource_scope.reset(token)

        return wrapper

    return decorator


def scoped_advisor_id(requested: str) -> str:
    """Plain advisors can only ever act as themselves; manager/admin may pass
    another advisor_id to see cross-advisor data, per the resource scope
    authorize() resolved from policy. Over stdio (no authenticated advisor in
    context) this is a no-op -- the caller-supplied ID passes through
    unchanged, matching pre-RBAC behavior."""
    advisor = current_advisor.get()
    if advisor is not None and _resource_scope.get() == "self":
        return advisor.id
    return requested


def owns_client(client) -> bool:
    """True if the current caller may act on this client: it's their own
    lead, the resolved policy scope is "*" (cross-advisor role), or there's
    no authenticated advisor in context at all (stdio transport)."""
    advisor = current_advisor.get()
    if advisor is None:
        return True
    return _resource_scope.get() == "*" or client.advisor_id == advisor.id
