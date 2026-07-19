import pytest

from app.mcp import server
from app.mcp.auth_middleware import current_advisor
from app.mcp.policy_engine import evaluate
from app.mcp.rbac import authorize, scoped_advisor_id, owns_client
from app.models.advisor import Advisor
from app.models.client import Client


def _set_advisor(role: str, advisor_id: str = "adv-1"):
    advisor = Advisor(id=advisor_id, name="T", email=f"{advisor_id}@x.com", phone="1", role=role)
    return current_advisor.set(advisor)


# ── policy_engine.evaluate: pure unit tests, no contextvars/DB needed ───


def test_evaluate_unknown_role_is_denied():
    assert evaluate("nonexistent-role", "mcp:list_leads").allowed is False


def test_evaluate_advisor_allowed_read_action_scoped_to_self():
    decision = evaluate("advisor", "mcp:list_leads")
    assert decision.allowed is True
    assert decision.resource_scope == "self"


def test_evaluate_advisor_denied_write_action():
    assert evaluate("advisor", "mcp:create_lead").allowed is False
    assert evaluate("advisor", "mcp:update_lead_status").allowed is False


def test_evaluate_manager_allowed_any_action_scoped_to_all():
    decision = evaluate("manager", "mcp:create_lead")
    assert decision.allowed is True
    assert decision.resource_scope == "*"


def test_evaluate_admin_matches_manager():
    decision = evaluate("admin", "mcp:update_lead_status")
    assert decision.allowed is True
    assert decision.resource_scope == "*"


def test_evaluate_stdio_no_role_is_unrestricted():
    decision = evaluate(None, "mcp:create_lead")
    assert decision.allowed is True
    assert decision.resource_scope == "*"


# ── authorize(): the decorator's own gating behavior ─────────────────────


@pytest.mark.asyncio
async def test_authorize_allows_stdio_no_advisor_in_context():
    """No advisor in context means stdio transport (no HTTP middleware ran) --
    treated as a trusted local process, not an unauthenticated HTTP request."""
    @authorize("mcp:create_lead")
    async def tool():
        return "ok"

    assert await tool() == "ok"


@pytest.mark.asyncio
async def test_authorize_blocks_denied_action():
    token = _set_advisor("advisor")
    try:
        @authorize("mcp:create_lead")
        async def tool():
            return "ok"

        assert "forbidden" in await tool()
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_authorize_allows_permitted_action():
    token = _set_advisor("manager")
    try:
        @authorize("mcp:create_lead")
        async def tool():
            return "ok"

        assert await tool() == "ok"
    finally:
        current_advisor.reset(token)


# ── scoped_advisor_id / owns_client: driven by authorize()'s resolved scope


@pytest.mark.asyncio
async def test_scoped_advisor_id_forces_own_id_for_plain_advisor():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        @authorize("mcp:list_leads")
        async def tool(requested_id):
            return scoped_advisor_id(requested_id)

        assert await tool("someone-elses-id") == "adv-1"
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_scoped_advisor_id_allows_cross_advisor_for_manager():
    token = _set_advisor("manager", advisor_id="mgr-1")
    try:
        @authorize("mcp:list_leads")
        async def tool(requested_id):
            return scoped_advisor_id(requested_id)

        assert await tool("someone-elses-id") == "someone-elses-id"
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_owns_client_true_for_own_client():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        @authorize("mcp:get_client")
        async def tool(client):
            return owns_client(client)

        assert await tool(Client(advisor_id="adv-1", name="Lead")) is True
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_owns_client_false_for_other_advisors_client():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        @authorize("mcp:get_client")
        async def tool(client):
            return owns_client(client)

        assert await tool(Client(advisor_id="someone-else", name="Lead")) is False
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_owns_client_true_for_manager_regardless_of_owner():
    token = _set_advisor("manager", advisor_id="mgr-1")
    try:
        @authorize("mcp:get_client")
        async def tool(client):
            return owns_client(client)

        assert await tool(Client(advisor_id="someone-else", name="Lead")) is True
    finally:
        current_advisor.reset(token)


def test_scoped_advisor_id_passthrough_for_stdio_no_advisor_in_context():
    assert current_advisor.get() is None
    assert scoped_advisor_id("whatever-id") == "whatever-id"


def test_owns_client_true_for_stdio_no_advisor_in_context():
    assert current_advisor.get() is None
    client = Client(advisor_id="anyone", name="Lead")
    assert owns_client(client) is True


# ── create_lead / update_lead_status: manager/admin only, via policy ────


@pytest.mark.asyncio
async def test_create_lead_blocked_for_plain_advisor():
    token = _set_advisor("advisor")
    try:
        result = await server.create_lead(advisor_id="adv-1", name="Lead")
        assert "forbidden" in result
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_update_lead_status_blocked_for_plain_advisor():
    token = _set_advisor("advisor")
    try:
        result = await server.update_lead_status(client_id="c-1", status="contacted")
        assert "forbidden" in result
    finally:
        current_advisor.reset(token)
