import fnmatch
from dataclasses import dataclass

from app.mcp.policies import POLICIES


@dataclass(frozen=True)
class Decision:
    allowed: bool
    resource_scope: str  # "self" or "*"


def evaluate(role: str | None, action: str) -> Decision:
    """IAM-style policy evaluation: default deny, an explicit Allow is
    required, and any explicit Deny wins over any Allow for the same action
    -- regardless of statement order, matching AWS IAM's evaluation logic.

    role=None means no authenticated caller in context, i.e. the stdio
    transport (see app/mcp/auth_middleware.py) -- treated as unrestricted,
    matching pre-policy-engine behavior for that trusted local transport.
    """
    if role is None:
        return Decision(allowed=True, resource_scope="*")

    allow_matched = False
    deny_matched = False
    scope = "self"

    for statement in POLICIES.get(role, []):
        if not any(fnmatch.fnmatch(action, pattern) for pattern in statement["action"]):
            continue
        if statement["effect"] == "Allow":
            allow_matched = True
            if statement.get("resource") == "*":
                scope = "*"
        elif statement["effect"] == "Deny":
            deny_matched = True

    return Decision(allowed=allow_matched and not deny_matched, resource_scope=scope)
