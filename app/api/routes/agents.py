import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

from app.agents.needs_analysis_agent import build_needs_analysis_agent
from app.agents.product_matching_agent import build_product_matching_agent
from app.agents.lead_nurturing_agent import build_lead_nurturing_agent
from app.agents.objection_handler_agent import build_objection_handler_agent
from app.agents.policy_research_agent import build_policy_research_agent
from app.agents.claims_renewals_agent import build_renewals_agent

router = APIRouter(prefix="/api/v1/agent", tags=["agents"])


# ── Request models ─────────────────────────────────────────────────────────

class AnalyzeLeadRequest(BaseModel):
    client_id: str

class MatchProductsRequest(BaseModel):
    client_id: str

class NurtureLeadRequest(BaseModel):
    client_id: str
    advisor_id: str

class HandleObjectionRequest(BaseModel):
    client_id: str
    objection: str

class ResearchPolicyRequest(BaseModel):
    question: str
    advisor_id: str

class RenewalsRequest(BaseModel):
    advisor_id: str
    days_ahead: int = 30


# ── Debug: expose raw traceback so we can see what's failing ──────────────
@router.post("/debug/interaction-insert")
async def debug_interaction_insert(client_id: str):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("""
                INSERT INTO interactions (id, client_id, interaction_type, notes, created_at)
                VALUES (gen_random_uuid()::text, :client_id, 'debug_test', 'debug', now())
                RETURNING id
            """), {"client_id": client_id})
            row = result.fetchone()
            await db.commit()
        return {"ok": True, "id": str(row.id)}
    except Exception as e:
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}


@router.post("/debug/client-lookup")
async def debug_client_lookup(client_id: str):
    try:
        from sqlalchemy import select
        from app.models.client import Client
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(Client).where(Client.id == client_id))).scalar_one_or_none()
        return {"found": row is not None, "name": row.name if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}


# ── 1. Needs Analysis Agent ────────────────────────────────────────────────
# Loads client → builds RAG query → fetches context → runs LLM analysis →
# extracts structured gaps → saves interaction record.
# Richer than /analyze-client: returns structured gaps + saves to DB.

@router.post("/analyze-lead")
async def agent_analyze_lead(data: AnalyzeLeadRequest):
    agent = build_needs_analysis_agent()
    result = await agent.ainvoke({
        "client_id": data.client_id,
        "client_profile": {}, "rag_query": "", "rag_context": "",
        "analysis_text": "", "gaps": [], "interaction_id": "", "errors": [],
    })
    if result.get("errors"):
        raise HTTPException(status_code=404, detail=result["errors"][0])
    return {
        "client_id": data.client_id,
        "analysis": result["analysis_text"],
        "gaps": result["gaps"],
        "interaction_id": result["interaction_id"],
    }


# ── 2. Product Matching Agent ──────────────────────────────────────────────
# Loads client → runs needs analysis → LLM generates 3 targeted search queries →
# runs all queries in parallel against vector store → deduplicates chunks →
# LLM ranks top 3 products with client_fit_score → saves to interactions.
# Better than /recommend-products: parallel search + fit scoring + saved record.

@router.post("/match-products")
async def agent_match_products(data: MatchProductsRequest):
    agent = build_product_matching_agent()
    result = await agent.ainvoke({
        "client_id": data.client_id,
        "client_profile": {}, "need_analysis": "",
        "search_queries": [], "raw_chunks": [], "recommendations": [], "errors": [],
    })
    if result.get("errors"):
        raise HTTPException(status_code=404, detail=result["errors"][0])
    return {
        "client_id": data.client_id,
        "need_analysis": result["need_analysis"],
        "recommendations": result["recommendations"],
    }


# ── 3. Lead Nurturing Agent ────────────────────────────────────────────────
# Orchestrates: Needs Analysis Agent → Product Matching Agent → draft follow-up
# email → queues email in approval_queue (pending advisor approval).
# One call replaces three manual steps + requires human approval before sending.

@router.post("/nurture-lead")
async def agent_nurture_lead(data: NurtureLeadRequest):
    agent = build_lead_nurturing_agent()
    result = await agent.ainvoke({
        "client_id": data.client_id,
        "advisor_id": data.advisor_id,
        "client_profile": {}, "need_analysis": "", "gaps": [],
        "recommendations": [], "draft_email": {}, "approval_id": "", "errors": [],
    })
    if result.get("errors"):
        raise HTTPException(status_code=404, detail=result["errors"][0])
    return {
        "client_id": data.client_id,
        "gaps": result["gaps"],
        "recommendations": result["recommendations"],
        "draft_email": result["draft_email"],
        "approval_id": result["approval_id"],
        "status": "queued_for_approval",
    }


# ── 4. Objection Handler Agent ─────────────────────────────────────────────
# Loads client → classifies objection into one of 7 types → generates
# structured response (empathy + reframe + strong_reason + client_specific) →
# suggests closing pitch line → logs interaction to DB.
# Better than /handle-objection: classifies type + suggests closing line + logs.

@router.post("/handle-objection")
async def agent_handle_objection(data: HandleObjectionRequest):
    agent = build_objection_handler_agent()
    result = await agent.ainvoke({
        "client_id": data.client_id,
        "objection": data.objection,
        "client_profile": {}, "objection_type": "",
        "structured_response": {}, "next_pitch": "",
        "interaction_id": "", "errors": [],
    })
    if result.get("errors"):
        raise HTTPException(status_code=404, detail=result["errors"][0])
    return {
        "client_id": data.client_id,
        "objection": data.objection,
        "objection_type": result["objection_type"],
        "response": result["structured_response"],
        "next_pitch": result["next_pitch"],
        "interaction_id": result["interaction_id"],
    }


# ── 5. Policy Research Agent ───────────────────────────────────────────────
# LLM plans 1–3 search queries → runs them sequentially against vector store,
# looping until sufficient context is gathered → validates answer has content →
# synthesizes a cited answer using only retrieved excerpts.
# The only iterative RAG agent — loops until it has enough context.

@router.post("/research-policy")
async def agent_research_policy(data: ResearchPolicyRequest):
    agent = build_policy_research_agent()
    result = await agent.ainvoke({
        "question": data.question,
        "advisor_id": data.advisor_id,
        "search_plan": [], "search_results": [],
        "searches_done": 0, "is_sufficient": False,
        "answer": "", "citations": [], "errors": [],
    })
    if result.get("errors"):
        raise HTTPException(status_code=400, detail=result["errors"][0])
    return {
        "question": data.question,
        "answer": result["answer"],
        "citations": result["citations"],
        "searches_done": result["searches_done"],
    }


# ── 6. Claims & Renewals Agent ────────────────────────────────────────────
# Loads all policies due within days_ahead → LLM scores each by lapse risk →
# filters to top 10 high-risk renewals → drafts personalised email + WhatsApp
# outreach for each → queues all in approval_queue → emails advisor summary.
# Only agent that handles bulk multi-client work in one call.

@router.post("/renewals")
async def agent_renewals(data: RenewalsRequest):
    agent = build_renewals_agent()
    result = await agent.ainvoke({
        "advisor_id": data.advisor_id,
        "days_ahead": data.days_ahead,
        "renewals": [], "scored_renewals": [],
        "priority_renewals": [], "draft_messages": [],
        "approval_ids": [], "errors": [],
    })
    errors = result.get("errors", [])
    if errors and errors != ["No upcoming renewals found"]:
        raise HTTPException(status_code=400, detail=errors[0])
    return {
        "advisor_id": data.advisor_id,
        "days_ahead": data.days_ahead,
        "renewals_found": len(result.get("renewals", [])),
        "priority_count": len(result.get("priority_renewals", [])),
        "approval_ids": result.get("approval_ids", []),
        "status": "queued_for_approval" if result.get("approval_ids") else "no_high_risk_renewals",
    }
