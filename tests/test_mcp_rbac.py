import pytest

from app.mcp import server
from app.mcp.auth_middleware import current_advisor
from app.mcp.rbac import require_role, scoped_advisor_id, owns_client
from app.models.advisor import Advisor
from app.models.client import Client


def _set_advisor(role: str, advisor_id: str = "adv-1"):
    advisor = Advisor(id=advisor_id, name="T", email=f"{advisor_id}@x.com", phone="1", role=role)
    return current_advisor.set(advisor)


@pytest.mark.asyncio
async def test_require_role_allows_stdio_no_advisor_in_context():
    """No advisor in context means stdio transport (no HTTP middleware ran) --
    treated as a trusted local process, not an unauthenticated HTTP request."""
    @require_role("advisor")
    async def tool():
        return "ok"

    assert await tool() == "ok"


@pytest.mark.asyncio
async def test_require_role_blocks_wrong_role():
    token = _set_advisor("advisor")
    try:
        @require_role("manager", "admin")
        async def tool():
            return "ok"

        assert "forbidden" in await tool()
    finally:
        current_advisor.reset(token)


@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    token = _set_advisor("manager")
    try:
        @require_role("manager", "admin")
        async def tool():
            return "ok"

        assert await tool() == "ok"
    finally:
        current_advisor.reset(token)


def test_scoped_advisor_id_forces_own_id_for_plain_advisor():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        assert scoped_advisor_id("someone-elses-id") == "adv-1"
    finally:
        current_advisor.reset(token)


def test_scoped_advisor_id_allows_cross_advisor_for_manager():
    token = _set_advisor("manager", advisor_id="mgr-1")
    try:
        assert scoped_advisor_id("someone-elses-id") == "someone-elses-id"
    finally:
        current_advisor.reset(token)


def test_owns_client_true_for_own_client():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        client = Client(advisor_id="adv-1", name="Lead")
        assert owns_client(client) is True
    finally:
        current_advisor.reset(token)


def test_owns_client_false_for_other_advisors_client():
    token = _set_advisor("advisor", advisor_id="adv-1")
    try:
        client = Client(advisor_id="someone-else", name="Lead")
        assert owns_client(client) is False
    finally:
        current_advisor.reset(token)


def test_owns_client_true_for_manager_regardless_of_owner():
    token = _set_advisor("manager", advisor_id="mgr-1")
    try:
        client = Client(advisor_id="someone-else", name="Lead")
        assert owns_client(client) is True
    finally:
        current_advisor.reset(token)


def test_scoped_advisor_id_passthrough_for_stdio_no_advisor_in_context():
    assert current_advisor.get() is None
    assert scoped_advisor_id("whatever-id") == "whatever-id"


def test_owns_client_true_for_stdio_no_advisor_in_context():
    assert current_advisor.get() is None
    client = Client(advisor_id="anyone", name="Lead")
    assert owns_client(client) is True


# ── create_lead / update_lead_status: manager/admin only ────────────────


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
