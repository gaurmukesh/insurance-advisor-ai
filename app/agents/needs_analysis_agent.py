import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs
from app.core.llm import chat


class NeedsAnalysisState(TypedDict):
    client_id: str
    client_profile: dict
    rag_query: str
    rag_context: str
    analysis_text: str
    gaps: list[dict]        # [{gap, priority, product_type}]
    interaction_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: NeedsAnalysisState) -> dict:
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


async def build_rag_query(state: NeedsAnalysisState) -> dict:
    p = state["client_profile"]
    query = (
        f"insurance coverage for {p.get('goals', 'general')} "
        f"age {p.get('age')} {p.get('employment_type', '')} "
        f"family size {p.get('family_size')} "
        f"health {p.get('health_conditions', 'none')}"
    )
    return {"rag_query": query}


async def fetch_context(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, state["rag_query"], top_k=5)
    context = "\n\n".join(r["content"] for r in results) if results else ""
    return {"rag_context": context}


async def run_analysis(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        analysis = await analyze_client_needs(db, state["client_profile"])
    return {"analysis_text": analysis}


async def extract_gaps(state: NeedsAnalysisState) -> dict:
    prompt = f"""Extract insurance gaps from this analysis as a JSON array.
Each item: {{"gap":"...","priority":"high|medium|low","product_type":"term|health|motor|ulip|personal_accident"}}
Return JSON only.

Analysis:
{state['analysis_text']}"""
    raw = await chat(
        "Extract structured data from insurance analysis. Return JSON only.",
        prompt, trace_name="extract_gaps"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        gaps = json.loads(clean)
    except Exception:
        gaps = []
    return {"gaps": gaps}


async def save_interaction(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO interactions (client_id, interaction_type, notes, created_at)
            VALUES (:client_id, 'ai_needs_analysis', :notes, now())
            RETURNING id
        """), {"client_id": state["client_id"], "notes": state["analysis_text"][:1000]})
        row = result.fetchone()
        await db.commit()
    return {"interaction_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_needs_analysis_agent():
    g = StateGraph(NeedsAnalysisState)
    g.add_node("load_client",      load_client)
    g.add_node("build_rag_query",  build_rag_query)
    g.add_node("fetch_context",    fetch_context)
    g.add_node("run_analysis",     run_analysis)
    g.add_node("extract_gaps",     extract_gaps)
    g.add_node("save_interaction", save_interaction)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "build_rag_query", "error": END})
    g.add_edge("build_rag_query",  "fetch_context")
    g.add_edge("fetch_context",    "run_analysis")
    g.add_edge("run_analysis",     "extract_gaps")
    g.add_edge("extract_gaps",     "save_interaction")
    g.add_edge("save_interaction", END)
    return g.compile()
