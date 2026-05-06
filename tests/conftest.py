"""
Shared fixtures for E2E tests.

Uses a real PostgreSQL test database (same docker-compose `db` service, separate DB name).
External services (OpenAI, SendGrid) are patched so tests run without live API keys.

Isolation strategy: override get_db to use the test engine so all route-level
DB operations hit `insurance_ai_test`. After each test, truncate all tables so
the next test starts clean. This avoids the asyncpg savepoint incompatibility
with connection-level transaction rollbacks.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.postgres import Base, get_db
from app.core.config import settings

# Import all models so Base.metadata includes every table before create_all runs.
# Use aliased imports to avoid shadowing the FastAPI `app` instance imported above.
import app.models.advisor as _m_advisor  # noqa: F401
import app.models.client as _m_client  # noqa: F401
import app.models.policy as _m_policy  # noqa: F401
import app.models.email_log as _m_email_log  # noqa: F401
import app.models.interaction as _m_interaction  # noqa: F401

# ── Test database ──────────────────────────────────────────────────────────────
TEST_DB_URL = settings.DATABASE_URL.replace("/insurance_ai", "/insurance_ai_test")

# NullPool prevents connection reuse across event loop boundaries.
# pytest-asyncio 0.23.x creates a new event loop per test function; pooled
# connections from a previous loop would trigger asyncpg's cross-loop error.
test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

_TRUNCATE_ALL = text(
    "TRUNCATE advisors, clients, policies, email_logs, interactions RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_schema():
    """Create all tables once for the whole test session, then drop them."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """
    Override get_db with a session backed by the test engine, and truncate
    all data after each test so every test starts with a clean slate.
    """
    async def test_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = test_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

    async with test_engine.begin() as conn:
        await conn.execute(_TRUNCATE_ALL)


@pytest_asyncio.fixture
async def db_session():
    """Yield a test-DB session for direct inserts in test fixtures."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Patch LLM chat functions so no real OpenAI calls are made."""
    with patch("app.modules.need_analyzer.chat", new_callable=AsyncMock) as mock_analyze, \
         patch("app.modules.product_recommender.chat", new_callable=AsyncMock) as mock_recommend, \
         patch("app.modules.email_generator.chat", new_callable=AsyncMock) as mock_email:
        mock_analyze.return_value = (
            "MOCK ANALYSIS: Client needs term life cover and health insurance. "
            "Priority: HIGH - Term Plan ₹1Cr, MEDIUM - Health cover ₹5L."
        )
        mock_recommend.return_value = (
            "MOCK RECOMMENDATIONS:\n"
            "1. LIC Tech Term - ₹8,000/yr - ₹1Cr SA\n"
            "2. Star Health Family Floater - ₹12,000/yr - ₹5L SA\n"
            "3. HDFC ERGO Personal Accident - ₹3,000/yr"
        )
        mock_email.return_value = "SUBJECT: Premium Reminder\nBODY:\nThis is a mocked email body."
        yield {"analyze": mock_analyze, "recommend": mock_recommend, "email": mock_email}


@pytest.fixture
def mock_rag():
    """Patch RAG retrieval so tests don't require a populated vector store."""
    with patch("app.modules.need_analyzer.retrieve_context", new_callable=AsyncMock) as m1, \
         patch("app.modules.product_recommender.retrieve_context", new_callable=AsyncMock) as m2:
        m1.return_value = "No specific policy documents available."
        m2.return_value = "No specific policy documents available."
        yield


@pytest.fixture
def mock_sendgrid():
    """Patch SendGrid so no real emails are sent."""
    with patch("app.api.routes.emails.send_email", return_value=True) as mock:
        yield mock
