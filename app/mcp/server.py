import json
from datetime import date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal
# Import all models so SQLAlchemy can resolve every relationship at startup
from app.models.advisor import Advisor  # noqa: F401
from app.models.interaction import Interaction  # noqa: F401
from app.models.email_log import EmailLog  # noqa: F401
from app.models.whatsapp_log import WhatsAppLog  # noqa: F401
from app.models.client import Client
from app.models.policy import Policy
from app.modules.need_analyzer import analyze_client_needs
from app.modules.product_recommender import recommend_products
from app.modules.pitch_handler import generate_pitch, handle_objection
from app.db.vector_store import similarity_search
from app.mcp.rbac import require_role, scoped_advisor_id, owns_client

_ANY_ROLE = ("advisor", "manager", "admin")
# create_lead / update_lead_status are restricted to manager/admin.
_WRITE_ROLE = ("manager", "admin")

mcp = FastMCP(
    "Insurance Advisor AI",
    instructions=(
        "Tools for managing insurance leads, running AI need analysis, "
        "generating product recommendations, pitches, handling objections, "
        "and searching policy documents."
    ),
)


def _to_dict(c: Client) -> dict:
    return {
        "id": c.id, "advisor_id": c.advisor_id, "name": c.name,
        "email": c.email, "phone": c.phone, "age": c.age,
        "income": c.income, "family_size": c.family_size,
        "risk_appetite": c.risk_appetite, "goals": c.goals,
        "status": c.status, "notes": c.notes,
        "existing_coverage": c.existing_coverage,
        "liabilities_emi": c.liabilities_emi,
        "employment_type": c.employment_type,
        "health_conditions": c.health_conditions,
        "dependents_detail": c.dependents_detail,
        "city_tier": c.city_tier,
    }


# ── TOOL 1: List leads ────────────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def list_leads(advisor_id: str, status: Optional[str] = None) -> str:
    """List all leads for an advisor.
    status options: new | contacted | interested | converted | lost"""
    advisor_id = scoped_advisor_id(advisor_id)
    async with AsyncSessionLocal() as db:
        q = select(Client).where(Client.advisor_id == advisor_id)
        if status:
            q = q.where(Client.status == status)
        q = q.order_by(Client.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return json.dumps([_to_dict(c) for c in rows], default=str)


# ── TOOL 2: Get client ────────────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def get_client(client_id: str) -> str:
    """Get the full profile of a lead by their ID."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        return json.dumps(_to_dict(row), default=str)


# ── TOOL 3: Create lead ───────────────────────────────────────────
@mcp.tool()
@require_role(*_WRITE_ROLE)
async def create_lead(
    advisor_id: str, name: str,
    email: Optional[str] = None, phone: Optional[str] = None,
    age: Optional[int] = None, income: Optional[float] = None,
    family_size: Optional[int] = None,
    risk_appetite: Optional[str] = None,
    goals: Optional[str] = None,
    employment_type: Optional[str] = None,
    health_conditions: Optional[str] = None,
    city_tier: Optional[str] = None,
) -> str:
    """Create a new insurance lead for an advisor."""
    advisor_id = scoped_advisor_id(advisor_id)
    async with AsyncSessionLocal() as db:
        client = Client(
            advisor_id=advisor_id, name=name, email=email, phone=phone,
            age=age, income=income, family_size=family_size,
            risk_appetite=risk_appetite, goals=goals,
            employment_type=employment_type,
            health_conditions=health_conditions, city_tier=city_tier,
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
        return json.dumps(_to_dict(client), default=str)


# ── TOOL 4: Update lead status ────────────────────────────────────
@mcp.tool()
@require_role(*_WRITE_ROLE)
async def update_lead_status(
    client_id: str, status: str, notes: Optional[str] = None
) -> str:
    """Update a lead's status and optionally add notes.
    status options: new | contacted | interested | converted | lost"""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        row.status = status
        if notes:
            row.notes = notes
        await db.commit()
        await db.refresh(row)
        return json.dumps(_to_dict(row), default=str)


# ── TOOL 5: Analyze needs ─────────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def analyze_needs(client_id: str) -> str:
    """Run AI-powered insurance need analysis.
    Identifies gaps, priorities, and tax benefit opportunities (80C/80D)."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        return await analyze_client_needs(db, _to_dict(row))


# ── TOOL 6: Get recommendations ───────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def get_recommendations(client_id: str) -> str:
    """Get top-3 AI-recommended insurance products for a client.
    Returns JSON with product, insurer, premium, sum assured, tax benefit."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        profile = _to_dict(row)
        need_analysis = await analyze_client_needs(db, profile)
        recs = await recommend_products(db, profile, need_analysis)
        return json.dumps(recs, default=str)


# ── TOOL 7: Generate pitch ────────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def generate_sales_pitch(client_id: str) -> str:
    """Generate a personalized sales pitch for a client.
    Format: Opening → Key Need → Solution → Call to Action."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        return await generate_pitch(_to_dict(row))


# ── TOOL 8: Handle objection ──────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def handle_client_objection(client_id: str, objection: str) -> str:
    """Get a structured response to a client objection.
    Common: 'premium too high', 'already have insurance', 'will think about it'"""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        if not owns_client(row):
            return json.dumps({"error": "forbidden"})
        result = await handle_objection(objection, _to_dict(row))
        return json.dumps(result, default=str)


# ── TOOL 9: Search policy docs ────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def search_policy_docs(query: str, top_k: int = 5) -> str:
    """Semantic search across ingested policy PDFs.
    Returns relevant excerpts with similarity scores."""
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, query, top_k=top_k)
        if not results:
            return "No relevant policy documents found."
        return json.dumps(results, default=str)


# ── TOOL 10: Upcoming renewals ────────────────────────────────────
@mcp.tool()
@require_role(*_ANY_ROLE)
async def get_upcoming_renewals(advisor_id: str, days: int = 30) -> str:
    """List policies due for renewal in the next N days."""
    advisor_id = scoped_advisor_id(advisor_id)
    async with AsyncSessionLocal() as db:
        today = date.today()
        until = today + timedelta(days=days)
        rows = (await db.execute(
            select(Policy, Client)
            .join(Client, Policy.client_id == Client.id)
            .where(Client.advisor_id == advisor_id)
            .where(Policy.next_due_date >= today)
            .where(Policy.next_due_date <= until)
            .order_by(Policy.next_due_date)
        )).all()
        return json.dumps([
            {
                "policy_id": p.id, "policy_no": p.policy_no,
                "product_name": p.product_name,
                "insurer_name": p.insurer_name,
                "premium_amount": p.premium_amount,
                "next_due_date": str(p.next_due_date),
                "client_id": c.id, "client_name": c.name,
                "client_email": c.email, "client_phone": c.phone,
            }
            for p, c in rows
        ], default=str)


if __name__ == "__main__":
    mcp.run()
