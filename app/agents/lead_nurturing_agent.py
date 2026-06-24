import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.modules.email_generator import generate_followup_email
from app.agents.needs_analysis_agent import build_needs_analysis_agent
from app.agents.product_matching_agent import build_product_matching_agent


class LeadNurturingState(TypedDict):
    client_id: str
    advisor_id: str
    client_profile: dict
    need_analysis: str
    gaps: list[dict]
    recommendations: list[dict]
    draft_email: dict
    approval_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: LeadNurturingState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "id": row.id, "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type,
        "health_conditions": row.health_conditions,
        "existing_coverage": row.existing_coverage,
        "city_tier": row.city_tier, "dependents_detail": row.dependents_detail,
    }}


async def run_needs_analysis_agent(state: LeadNurturingState) -> dict:
    agent = build_needs_analysis_agent()
    result = await agent.ainvoke({
        "client_id": state["client_id"], "client_profile": {},
        "rag_query": "", "rag_context": "", "analysis_text": "",
        "gaps": [], "interaction_id": "", "errors": [],
    })
    if result.get("errors"):
        return {"errors": result["errors"]}
    return {"need_analysis": result["analysis_text"], "gaps": result["gaps"]}


async def run_product_matching_agent(state: LeadNurturingState) -> dict:
    agent = build_product_matching_agent()
    result = await agent.ainvoke({
        "client_id": state["client_id"], "client_profile": {},
        "need_analysis": "", "search_queries": [],
        "raw_chunks": [], "recommendations": [], "errors": [],
    })
    if result.get("errors"):
        return {"errors": result["errors"]}
    return {"recommendations": result["recommendations"]}


async def draft_email(state: LeadNurturingState) -> dict:
    top = state.get("recommendations", [{}])[0] if state.get("recommendations") else {}
    email = await generate_followup_email(
        client_name=state["client_profile"]["name"],
        advisor_name="Your Advisor",
        context=(
            f"Top recommendation: {top.get('product_name', 'insurance plan')} "
            f"by {top.get('insurer', '')}. "
            f"Key benefit: {top.get('key_benefit', '')}."
        ),
    )
    return {"draft_email": email}


async def queue_approval(state: LeadNurturingState) -> dict:
    payload = json.dumps({
        "client_id": state["client_id"],
        "email": state["draft_email"],
        "recommendations": state["recommendations"],
        "gaps": state["gaps"],
    }, default=str)
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO approval_queue
                (client_id, advisor_id, action_type, payload, status, created_at)
            VALUES (:client_id, :advisor_id, 'send_nurturing_email', :payload, 'pending', now())
            RETURNING id
        """), {
            "client_id": state["client_id"],
            "advisor_id": state.get("advisor_id", ""),
            "payload": payload,
        })
        row = result.fetchone()
        await db.commit()
    return {"approval_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_lead_nurturing_agent():
    g = StateGraph(LeadNurturingState)
    g.add_node("load_client",                load_client)
    g.add_node("run_needs_analysis_agent",   run_needs_analysis_agent)
    g.add_node("run_product_matching_agent", run_product_matching_agent)
    g.add_node("draft_email",               draft_email)
    g.add_node("queue_approval",            queue_approval)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "run_needs_analysis_agent", "error": END})
    g.add_conditional_edges("run_needs_analysis_agent", _check_errors,
                            {"continue": "run_product_matching_agent", "error": END})
    g.add_conditional_edges("run_product_matching_agent", _check_errors,
                            {"continue": "draft_email", "error": END})
    g.add_edge("draft_email",    "queue_approval")
    g.add_edge("queue_approval", END)
    return g.compile()
