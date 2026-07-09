import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search, parse_chunk_metadata
from app.core.llm import chat
from app.core.guardrails import validate_input


class PolicyResearchState(TypedDict):
    question: str
    advisor_id: str
    search_plan: list[str]
    search_results: list[dict]
    searches_done: int
    is_sufficient: bool
    answer: str
    citations: list[str]
    errors: Annotated[list[str], operator.add]


async def receive_question(state: PolicyResearchState) -> dict:
    if not state.get("question"):
        return {"errors": ["No question provided"]}
    return {}


async def validate_scope(state: PolicyResearchState) -> dict:
    try:
        await validate_input(state["question"], context="policy_research")
    except ValueError as e:
        return {"errors": [str(e)]}
    return {}


async def plan_searches(state: PolicyResearchState) -> dict:
    prompt = f"""Break this insurance question into 1–3 specific search queries.
Return JSON array of strings only.

Question: {state['question']}"""
    raw = await chat(
        "Plan search queries for an insurance knowledge base. Return JSON array only.",
        prompt, trace_name="plan_searches"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(clean)[:3]
    except Exception:
        queries = [state["question"]]
    return {"search_plan": queries, "searches_done": 0, "is_sufficient": False}


async def search_loop(state: PolicyResearchState) -> dict:
    idx = state.get("searches_done", 0)
    queries = state.get("search_plan", [])
    if idx >= len(queries):
        return {"is_sufficient": True}
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, queries[idx], top_k=5)
    existing = state.get("search_results", [])
    seen = {c["content"][:100] for c in existing}
    new_chunks = [r for r in results if r["content"][:100] not in seen]
    return {
        "search_results": existing + new_chunks,
        "searches_done": idx + 1,
        "is_sufficient": (idx + 1) >= len(queries),
    }


async def validate_answer(state: PolicyResearchState) -> dict:
    if not state.get("search_results"):
        return {"errors": ["No policy documents found for this question"]}
    return {}


def _source_name(chunk: dict) -> str:
    return parse_chunk_metadata(chunk.get("metadata", "")).get("source") or "policy document"


async def synthesize_with_citations(state: PolicyResearchState) -> dict:
    context = "\n\n".join(
        f"[Source {i+1}: {_source_name(r)}]\n{r['content']}"
        for i, r in enumerate(state["search_results"][:8])
    )
    prompt = f"""Answer this insurance question using only the provided policy excerpts.
Cite sources as [Source N]. If the answer is not in the excerpts, say so clearly.

Question: {state['question']}

Policy Excerpts:
{context}"""
    answer = await chat(
        "Expert insurance document analyst. Answer with citations from provided excerpts only.",
        prompt, trace_name="synthesize_answer"
    )
    citations = [
        f"Source {i+1}: {_source_name(r)}"
        for i, r in enumerate(state["search_results"][:8])
    ]
    return {"answer": answer, "citations": citations}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def _check_sufficient(state) -> str:
    return "done" if state.get("is_sufficient") else "search_again"


def build_policy_research_agent():
    g = StateGraph(PolicyResearchState)
    g.add_node("receive_question",          receive_question)
    g.add_node("validate_scope",            validate_scope)
    g.add_node("plan_searches",             plan_searches)
    g.add_node("search_loop",              search_loop)
    g.add_node("validate_answer",           validate_answer)
    g.add_node("synthesize_with_citations", synthesize_with_citations)
    g.set_entry_point("receive_question")
    g.add_conditional_edges("receive_question", _check_errors,
                            {"continue": "validate_scope", "error": END})
    g.add_conditional_edges("validate_scope", _check_errors,
                            {"continue": "plan_searches", "error": END})
    g.add_edge("plan_searches", "search_loop")
    g.add_conditional_edges("search_loop", _check_sufficient,
                            {"done": "validate_answer", "search_again": "search_loop"})
    g.add_conditional_edges("validate_answer", _check_errors,
                            {"continue": "synthesize_with_citations", "error": END})
    g.add_edge("synthesize_with_citations", END)
    return g.compile()
