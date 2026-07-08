import pytest

from tests.conftest import ADVISOR_PASSWORD


@pytest.mark.asyncio
async def test_login_success(client, advisor):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": ADVISOR_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["advisor"]["email"] == advisor.email


@pytest.mark.asyncio
async def test_login_wrong_password(client, advisor):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_token_401(client):
    response = await client.get("/api/v1/leads")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token_401(client):
    response = await client.get(
        "/api/v1/leads", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_ownership_404_for_other_advisor(client, db_session, auth_headers):
    from app.models.advisor import Advisor
    from app.models.client import Client
    from app.core.security import hash_password

    other_advisor = Advisor(
        name="Other Advisor", email="other-advisor@example.com",
        phone="8888888888", password_hash=hash_password("irrelevant"),
    )
    db_session.add(other_advisor)
    await db_session.commit()
    await db_session.refresh(other_advisor)

    other_client = Client(advisor_id=other_advisor.id, name="Someone Else's Lead")
    db_session.add(other_client)
    await db_session.commit()
    await db_session.refresh(other_client)

    response = await client.get(f"/api/v1/leads/{other_client.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_own_lead(client, auth_headers):
    create_response = await client.post(
        "/api/v1/leads", json={"name": "My Lead"}, headers=auth_headers
    )
    assert create_response.status_code == 200
    lead = create_response.json()
    assert lead["name"] == "My Lead"

    list_response = await client.get("/api/v1/leads", headers=auth_headers)
    assert list_response.status_code == 200
    names = [c["name"] for c in list_response.json()]
    assert "My Lead" in names
