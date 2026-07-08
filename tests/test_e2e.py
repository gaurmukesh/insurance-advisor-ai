"""
End-to-end tests for Insurance Advisor AI.

Each test class covers one complete user journey, calling real API endpoints
against a real (test) database. External services (OpenAI, SendGrid) are mocked.

Journeys tested:
  1. Lead lifecycle       — create → update status → fetch
  2. AI advisory flow     — create lead → analyze needs → get recommendations
  3. Policy & renewals    — add policy → query upcoming renewals
  4. Email drafting       — draft reminder → draft follow-up
  5. Email sending        — send reminder → verify email log persisted
  6. Health check         — sanity check the /health endpoint
"""

import pytest
import pytest_asyncio
from datetime import date, timedelta


# ── Helpers ────────────────────────────────────────────────────────────────────

ADVISOR_ID = "advisor-test-001"

SAMPLE_CLIENT = {
    "advisor_id": ADVISOR_ID,
    "name": "Rajesh Kumar",
    "email": "rajesh.kumar@example.com",
    "phone": "9876543210",
    "age": 35,
    "income": 1200000.0,
    "family_size": 4,
    "risk_appetite": "medium",
    "goals": "retirement planning, child education, family protection",
}


async def _create_client(client, auth_headers, payload=None) -> dict:
    resp = await client.post("/api/v1/leads", json=payload or SAMPLE_CLIENT, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


ADVISOR_PASSWORD = "test-password-e2e"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_advisor(db_session):
    """Insert a minimal Advisor row so the clients FK constraint is satisfied."""
    from app.core.security import hash_password
    from app.models.advisor import Advisor

    advisor = Advisor(
        id=ADVISOR_ID,
        name="Test Advisor",
        email="test.advisor@example.com",
        phone="9999999999",
        password_hash=hash_password(ADVISOR_PASSWORD),
    )
    db_session.add(advisor)
    await db_session.commit()


@pytest_asyncio.fixture
async def auth_headers(client, db_advisor):
    """Authorization header for the fixed-id `db_advisor` used throughout this suite."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test.advisor@example.com", "password": ADVISOR_PASSWORD},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── 1. Lead Lifecycle ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestLeadLifecycle:

    async def test_create_lead_returns_client_with_id(self, client, auth_headers):
        data = await _create_client(client, auth_headers)
        assert data["id"]
        assert data["name"] == "Rajesh Kumar"
        assert data["status"] == "new"

    async def test_list_leads_returns_created_lead(self, client, auth_headers):
        await _create_client(client, auth_headers)
        resp = await client.get("/api/v1/leads", headers=auth_headers)
        assert resp.status_code == 200
        leads = resp.json()
        assert len(leads) >= 1
        assert leads[0]["name"] == "Rajesh Kumar"

    async def test_list_leads_filtered_by_status(self, client, auth_headers):
        created = await _create_client(client, auth_headers)
        client_id = created["id"]

        # Update to "interested"
        await client.put(
            f"/api/v1/leads/{client_id}", json={"status": "interested"}, headers=auth_headers
        )

        resp_new = await client.get("/api/v1/leads?status=new", headers=auth_headers)
        resp_interested = await client.get("/api/v1/leads?status=interested", headers=auth_headers)

        new_ids = [c["id"] for c in resp_new.json()]
        interested_ids = [c["id"] for c in resp_interested.json()]

        assert client_id not in new_ids
        assert client_id in interested_ids

    async def test_get_lead_by_id(self, client, auth_headers):
        created = await _create_client(client, auth_headers)
        resp = await client.get(f"/api/v1/leads/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "rajesh.kumar@example.com"

    async def test_get_lead_not_found_returns_404(self, client, auth_headers):
        resp = await client.get("/api/v1/leads/non-existent-id", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_lead_notes(self, client, auth_headers):
        created = await _create_client(client, auth_headers)
        resp = await client.put(
            f"/api/v1/leads/{created['id']}",
            json={"notes": "Interested in term plan, follow up next week"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "term plan" in resp.json()["notes"]


# ── 2. AI Advisory Flow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAIAdvisoryFlow:

    async def test_analyze_client_needs(self, client, auth_headers, mock_llm, mock_rag):
        created = await _create_client(client, auth_headers)
        resp = await client.post(
            "/api/v1/analyze-client",
            json={
                "client_id": created["id"],
                "existing_policies": "None",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["client_id"] == created["id"]
        assert "analysis" in body
        assert len(body["analysis"]) > 10
        mock_llm["analyze"].assert_called_once()

    async def test_recommend_products(self, client, auth_headers, mock_llm, mock_rag):
        created = await _create_client(client, auth_headers)
        resp = await client.post(
            "/api/v1/recommend-products",
            json={
                "client_id": created["id"],
                "need_analysis": "Client needs term and health insurance coverage.",
                "existing_policies": "None",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["client_id"] == created["id"]
        assert "recommendations" in body
        mock_llm["recommend"].assert_called_once()

    async def test_full_advisory_pipeline(self, client, auth_headers, mock_llm, mock_rag):
        """Create lead → analyze → recommend (full chain in one test)."""
        # Step 1: create lead
        lead = await _create_client(client, auth_headers)
        client_id = lead["id"]

        # Step 2: analyze needs
        analyze_resp = await client.post(
            "/api/v1/analyze-client",
            json={"client_id": client_id, "existing_policies": "LIC Jeevan Anand"},
            headers=auth_headers,
        )
        assert analyze_resp.status_code == 200
        analysis = analyze_resp.json()["analysis"]

        # Step 3: get product recommendations based on analysis
        recommend_resp = await client.post(
            "/api/v1/recommend-products",
            json={
                "client_id": client_id,
                "need_analysis": analysis,
                "existing_policies": "LIC Jeevan Anand",
            },
            headers=auth_headers,
        )
        assert recommend_resp.status_code == 200
        assert recommend_resp.json()["recommendations"]

    async def test_analyze_nonexistent_client_returns_404(self, client, auth_headers, mock_llm, mock_rag):
        resp = await client.post(
            "/api/v1/analyze-client",
            json={"client_id": "ghost-id"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── 3. Policy & Renewals ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client_with_policy(client, auth_headers, db_session):
    """Create a client via the API and attach a policy due in 10 days."""
    from app.models.policy import Policy

    lead = await _create_client(client, auth_headers)
    due_date = date.today() + timedelta(days=10)

    policy = Policy(
        client_id=lead["id"],
        insurer_name="LIC",
        product_name="Tech Term Plan",
        policy_no="LIC-TEST-001",
        policy_type="term",
        premium_amount=8500.0,
        sum_assured=10000000.0,
        next_due_date=due_date,
    )
    db_session.add(policy)
    await db_session.commit()
    await db_session.refresh(policy)

    return {"client": lead, "policy_id": policy.id, "due_date": due_date}


@pytest.mark.asyncio
class TestPolicyRenewals:

    async def test_upcoming_renewals_includes_policy_due_soon(self, client, client_with_policy, auth_headers):
        resp = await client.get("/api/v1/renewals/upcoming?days=30", headers=auth_headers)
        assert resp.status_code == 200
        renewals = resp.json()
        assert any(r["policy_no"] == "LIC-TEST-001" for r in renewals)

    async def test_renewals_excludes_policy_outside_window(self, client, client_with_policy, auth_headers):
        # Window of 5 days — our policy is due in 10 days, should not appear
        resp = await client.get("/api/v1/renewals/upcoming?days=5", headers=auth_headers)
        assert resp.status_code == 200
        renewals = resp.json()
        assert not any(r["policy_no"] == "LIC-TEST-001" for r in renewals)

    async def test_renewals_response_shape(self, client, client_with_policy, auth_headers):
        resp = await client.get("/api/v1/renewals/upcoming", headers=auth_headers)
        renewals = resp.json()
        if renewals:
            keys = renewals[0].keys()
            for field in ("policy_id", "client_name", "client_email", "next_due_date", "premium_amount"):
                assert field in keys


# ── 4. Email Drafting ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestEmailDrafting:

    async def test_draft_premium_reminder_email(self, client, client_with_policy, auth_headers, mock_llm):
        policy_id = client_with_policy["policy_id"]
        resp = await client.post(
            "/api/v1/draft-email/reminder",
            json={"policy_id": policy_id, "advisor_name": "Amit Singh"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "subject" in body
        assert "body" in body
        assert body["client_name"] == "Rajesh Kumar"

    async def test_draft_followup_email(self, client, auth_headers, mock_llm):
        lead = await _create_client(client, auth_headers)
        resp = await client.post(
            "/api/v1/draft-email/followup",
            json={
                "client_id": lead["id"],
                "advisor_name": "Amit Singh",
                "context": "Client expressed interest in health insurance last week.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "subject" in body
        assert "body" in body

    async def test_draft_reminder_invalid_policy_returns_404(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/draft-email/reminder",
            json={"policy_id": "invalid-id", "advisor_name": "Advisor"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── 5. Email Sending & Logging ─────────────────────────────────────────────────

@pytest.mark.asyncio
class TestEmailSending:

    async def test_send_reminder_records_email_log(
        self, client, client_with_policy, auth_headers, mock_sendgrid, mock_llm
    ):
        policy_id = client_with_policy["policy_id"]

        send_resp = await client.post(
            "/api/v1/send-email/reminder",
            json={"policy_id": policy_id, "advisor_name": "Amit Singh"},
            headers=auth_headers,
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["status"] == "sent"
        mock_sendgrid.assert_called_once()

        # Verify the log was persisted
        logs_resp = await client.get("/api/v1/email-logs", headers=auth_headers)
        assert logs_resp.status_code == 200
        logs = logs_resp.json()
        assert any(log["policy_id"] == policy_id for log in logs)

    async def test_send_reminder_client_without_email_returns_400(
        self, client, auth_headers, mock_llm, db_session
    ):
        from app.models.policy import Policy

        no_email_client = {**SAMPLE_CLIENT, "email": None}
        lead = await _create_client(client, auth_headers, payload=no_email_client)

        policy = Policy(
            client_id=lead["id"],
            insurer_name="HDFC Life",
            product_name="Click 2 Protect",
            policy_no="HDFC-NOEMAIL-001",
            policy_type="term",
            premium_amount=9000.0,
            next_due_date=date.today() + timedelta(days=5),
        )
        db_session.add(policy)
        await db_session.commit()
        await db_session.refresh(policy)

        resp = await client.post(
            "/api/v1/send-email/reminder",
            json={"policy_id": policy.id, "advisor_name": "Advisor"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower()


# ── 6. Health Check ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestHealth:

    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
