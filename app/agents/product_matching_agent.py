import json
import asyncio
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs
from app.core.llm import chat


class ProductMatchingState(TypedDict):
    client_id: str
    client_profile: dict
    need_analysis: str
    search_queries: list[str]   # LLM-generated targeted queries
    raw_chunks: list[dict]      # deduplicated chunks from all searches
    recommendations: list[dict] # ranked with client_fit_score
    errors: Annotated[list[str], operator.add]


async def load_client(state: ProductMatchingState) -> dict:
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
        "employment_type": row.employment_type or "Not specified",
        "health_conditions": row.health_conditions or "None",
        "existing_coverage": row.existing_coverage or "None",
        "city_tier": row.city_tier or "Not specified",
        "dependents_detail": row.dependents_detail or "None",
    }}


async def run_needs_analysis(state: ProductMatchingState) -> dict:
    async with AsyncSessionLocal() as db:
        analysis = await analyze_client_needs(db, state["client_profile"])
    return {"need_analysis": analysis}


async def generate_queries(state: ProductMatchingState) -> dict:
    p = state["client_profile"]
    prompt = f"""Generate 3 specific insurance product search queries for this client.
Each query targets a different coverage need.
Return JSON array of 3 strings only.

Client: Age {p.get('age')}, Income ₹{p.get('income',0):,.0f},
Goals: {p.get('goals')}, Health: {p.get('health_conditions')},
Risk: {p.get('risk_appetite')}, Existing: {p.get('existing_coverage')}
Need Analysis: {state['need_analysis'][:300]}"""
    raw = await chat(
        "Generate targeted insurance product search queries. Return JSON array only.",
        prompt, trace_name="gen_queries"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(clean)[:3]
    except Exception:
        queries = [
            f"{p.get('goals','')} insurance {p.get('risk_appetite','')} risk India",
            f"health insurance {p.get('health_conditions','general')} coverage India",
            f"term life insurance age {p.get('age')} income {p.get('income',0)}",
        ]
    return {"search_queries": queries}


async def search_products(state: ProductMatchingState) -> dict:
    async def one(q: str) -> list[dict]:
        async with AsyncSessionLocal() as db:
            return await similarity_search(db, q, top_k=6)

    results = await asyncio.gather(*[one(q) for q in state["search_queries"]])
    seen, chunks = set(), []
    for batch in results:
        for c in batch:
            key = c["content"][:100]
            if key not in seen:
                seen.add(key)
                chunks.append(c)
    return {"raw_chunks": chunks}


async def rank_match(state: ProductMatchingState) -> dict:
    p = state["client_profile"]
    context = "\n\n".join(c["content"] for c in state["raw_chunks"][:12])
    disposable = (p.get("income") or 0) / 12 - (p.get("liabilities_emi") or 0)
    prompt = f"""Recommend top 3 insurance products. Return JSON only.

Client: Age {p.get('age')}, Income ₹{p.get('income',0):,.0f},
Disposable ₹{disposable:,.0f}/mo, Family {p.get('family_size')},
Risk {p.get('risk_appetite')}, Goals: {p.get('goals')},
Health: {p.get('health_conditions')}, Existing: {p.get('existing_coverage')}

Policy Knowledge:
{context}

Return: [{{"rank":1,"product_name":"...","insurer":"...","type":"term|health|ulip|motor",
"premium_per_month":0,"sum_assured":"...","key_benefit":"...","why_suits":"...",
"tax_benefit":"80C|80D|none","client_fit_score":85,"pitch_first":true}}]
Only one item should have pitch_first=true."""
    raw = await chat(
        "Expert insurance product advisor. Return JSON only.",
        prompt, trace_name="rank_match"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        recs = json.loads(clean)
    except Exception:
        recs = []
    return {"recommendations": recs}


async def save_recs(state: ProductMatchingState) -> dict:
    if not state.get("recommendations"):
        return {}
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO interactions (id, client_id, interaction_type, notes, created_at)
            VALUES (gen_random_uuid()::text, :client_id, 'ai_product_recommendations', :notes, now())
        """), {
            "client_id": state["client_id"],
            "notes": json.dumps(state["recommendations"])[:2000],
        })
        await db.commit()
    return {}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_product_matching_agent():
    g = StateGraph(ProductMatchingState)
    g.add_node("load_client",        load_client)
    g.add_node("run_needs_analysis", run_needs_analysis)
    g.add_node("generate_queries",   generate_queries)
    g.add_node("search_products",    search_products)
    g.add_node("rank_match",         rank_match)
    g.add_node("save_recs",          save_recs)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "run_needs_analysis", "error": END})
    g.add_edge("run_needs_analysis", "generate_queries")
    g.add_edge("generate_queries",   "search_products")
    g.add_edge("search_products",    "rank_match")
    g.add_edge("rank_match",         "save_recs")
    g.add_edge("save_recs",          END)
    return g.compile()
