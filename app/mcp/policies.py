"""
Declarative, IAM-inspired authorization policies for MCP tools -- Allow/Deny
statements over Action/Resource, evaluated by app.mcp.policy_engine.evaluate().

Replaces the old require_role(*roles) tuples: adding a role or changing a
tool's access is a change to this document, not to a decorator argument
scattered across app/mcp/server.py.

"resource": "self" means the caller may only act on rows they own (enforced
by scoped_advisor_id/owns_client in app/mcp/rbac.py); "*" means any advisor's
data. An explicit Deny always overrides an Allow for the same action, exactly
as in AWS IAM policy evaluation.
"""

_READ_AND_ASSIST_ACTIONS = [
    "mcp:list_leads",
    "mcp:get_client",
    "mcp:analyze_needs",
    "mcp:get_recommendations",
    "mcp:generate_sales_pitch",
    "mcp:handle_client_objection",
    "mcp:search_policy_docs",
    "mcp:get_upcoming_renewals",
]

_WRITE_ACTIONS = [
    "mcp:create_lead",
    "mcp:update_lead_status",
]

POLICIES: dict[str, list[dict]] = {
    "advisor": [
        {"effect": "Allow", "action": _READ_AND_ASSIST_ACTIONS, "resource": "self"},
        {"effect": "Deny", "action": _WRITE_ACTIONS, "resource": "*"},
    ],
    "manager": [
        {"effect": "Allow", "action": ["mcp:*"], "resource": "*"},
    ],
    "admin": [
        {"effect": "Allow", "action": ["mcp:*"], "resource": "*"},
    ],
}
