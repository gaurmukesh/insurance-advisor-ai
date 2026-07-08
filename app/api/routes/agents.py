import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.needs_analysis_agent import build_needs_analysis_agent, extract_gaps, save_interaction
from app.agents.product_matching_agent import build_product_matching_agent
from app.agents.lead_nurturing_agent import build_lead_nurturing_agent
from app.agents.objection_handler_agent import build_objection_handler_agent
from app.agents.policy_research_agent import build_policy_research_agent
from app.agents.claims_renewals_agent import build_renewals_agent
from app.api.deps import get_current_advisor
from app.db.postgres import get_db
from app.models.advisor import Advisor
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs_stream

router = APIRouter(prefix="/api/v1/agent", tags=["agents"])


# ── Request models ─────────────────────────────────────────────────────────

class AnalyzeLeadRequest(BaseModel):
    client_id: str

class MatchProductsRequest(BaseModel):
    client_id: str

class NurtureLeadRequest(BaseModel):
    client_id: str

class HandleObjectionRequest(BaseModel):
    client_id: str
    objection: str

class ResearchPolicyRequest(BaseModel):
    question: str

class RenewalsRequest(BaseModel):
    days_ahead: int = 30


async def _verify_own_client(db: AsyncSession, client_id: str, advisor: Advisor) -> None:
    result = await db.execute(select(Client.advisor_id).where(Client.id == client_id))
    row = result.scalar_one_or_none()
    if row is None or row != advisor.id:
        raise HTTPException(status_code=404, detail="Client not found")


# ── 1. Needs Analysis Agent ────────────────────────────────────────────────
# Loads client → builds RAG query → fetches context → runs LLM analysis →
# extracts structured gaps → saves interaction record.
# Richer than /analyze-client: returns structured gaps + saves to DB.

@router.post("/analyze-lead")
async def agent_analyze_lead(
    data: AnalyzeLeadRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    await _verify_own_client(db, data.client_id, current)
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


# Streaming variant of the above — tokens arrive as they're generated instead of
# waiting ~15s for the full analysis. Same gap-extraction + DB save happen after
# the stream completes, emitted as a final `done` event.

@router.post("/analyze-lead/stream")
async def agent_analyze_lead_stream(
    data: AnalyzeLeadRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client or client.advisor_id != current.id:
        raise HTTPException(status_code=404, detail="Client not found")

    client_profile = {
        "id": client.id, "name": client.name, "age": client.age, "income": client.income,
        "family_size": client.family_size, "risk_appetite": client.risk_appetite,
        "goals": client.goals, "liabilities_emi": client.liabilities_emi or 0,
        "employment_type": client.employment_type or "Not specified",
        "health_conditions": client.health_conditions or "None",
        "existing_coverage": client.existing_coverage or "None",
        "city_tier": client.city_tier or "Not specified",
        "dependents_detail": client.dependents_detail or "None",
    }

    async def event_stream():
        chunks: list[str] = []
        async for token in analyze_client_needs_stream(db, client_profile):
            chunks.append(token)
            yield f"data: {json.dumps(token)}\n\n"

        full_text = "".join(chunks)
        gaps_result = await extract_gaps({"analysis_text": full_text})
        interaction_result = await save_interaction({
            "client_id": data.client_id, "analysis_text": full_text,
        })
        payload = {
            "gaps": gaps_result.get("gaps", []),
            "interaction_id": interaction_result.get("interaction_id", ""),
        }
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── 2. Product Matching Agent ──────────────────────────────────────────────
# Loads client → runs needs analysis → LLM generates 3 targeted search queries →
# runs all queries in parallel against vector store → deduplicates chunks →
# LLM ranks top 3 products with client_fit_score → saves to interactions.
# Better than /recommend-products: parallel search + fit scoring + saved record.

@router.post("/match-products")
async def agent_match_products(
    data: MatchProductsRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    await _verify_own_client(db, data.client_id, current)
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
async def agent_nurture_lead(
    data: NurtureLeadRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    await _verify_own_client(db, data.client_id, current)
    agent = build_lead_nurturing_agent()
    result = await agent.ainvoke({
        "client_id": data.client_id,
        "advisor_id": current.id,
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
async def agent_handle_objection(
    data: HandleObjectionRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    await _verify_own_client(db, data.client_id, current)
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
async def agent_research_policy(
    data: ResearchPolicyRequest,
    current: Advisor = Depends(get_current_advisor),
):
    agent = build_policy_research_agent()
    result = await agent.ainvoke({
        "question": data.question,
        "advisor_id": current.id,
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
async def agent_renewals(
    data: RenewalsRequest,
    current: Advisor = Depends(get_current_advisor),
):
    agent = build_renewals_agent()
    result = await agent.ainvoke({
        "advisor_id": current.id,
        "days_ahead": data.days_ahead,
        "renewals": [], "scored_renewals": [],
        "priority_renewals": [], "draft_messages": [],
        "approval_ids": [], "errors": [],
    })
    errors = result.get("errors", [])
    if errors and errors != ["No upcoming renewals found"]:
        raise HTTPException(status_code=400, detail=errors[0])
    return {
        "advisor_id": current.id,
        "days_ahead": data.days_ahead,
        "renewals_found": len(result.get("renewals", [])),
        "priority_count": len(result.get("priority_renewals", [])),
        "approval_ids": result.get("approval_ids", []),
        "status": "queued_for_approval" if result.get("approval_ids") else "no_high_risk_renewals",
    }
