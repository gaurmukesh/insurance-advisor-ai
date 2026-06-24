import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.modules.pitch_handler import handle_objection
from app.core.llm import chat_mini


OBJECTION_TYPES = [
    "premium_too_high", "already_have_insurance", "will_think_about_it",
    "dont_trust_insurers", "young_and_healthy", "no_time", "employer_covers_me",
]


class ObjectionHandlerState(TypedDict):
    client_id: str
    objection: str
    client_profile: dict
    objection_type: str
    structured_response: dict
    next_pitch: str
    interaction_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: ObjectionHandlerState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type,
        "health_conditions": row.health_conditions,
        "existing_policies": row.existing_coverage,
    }}


async def classify_objection(state: ObjectionHandlerState) -> dict:
    prompt = f"""Classify this objection into one of: {', '.join(OBJECTION_TYPES)}
Return the category string only, nothing else.

Objection: "{state['objection']}"
"""
    raw = await chat_mini(
        "Classify insurance objections into categories.",
        prompt, trace_name="classify_objection"
    )
    objection_type = raw.strip().lower().replace(" ", "_")
    if objection_type not in OBJECTION_TYPES:
        objection_type = "will_think_about_it"
    return {"objection_type": objection_type}


async def generate_response(state: ObjectionHandlerState) -> dict:
    response = await handle_objection(state["objection"], state["client_profile"])
    return {"structured_response": response}


async def suggest_next_pitch(state: ObjectionHandlerState) -> dict:
    p = state["client_profile"]
    prompt = f"""The advisor just handled this objection. Suggest ONE confident closing line.

Objection type: {state['objection_type']}
Response given: {json.dumps(state['structured_response'])}
Client: {p.get('name')}, age {p.get('age')}, goals: {p.get('goals')}

Return just the closing line, nothing else."""
    pitch = await chat_mini(
        "Insurance sales coach. Suggest a closing line.",
        prompt, trace_name="suggest_next_pitch"
    )
    return {"next_pitch": pitch.strip()}


async def log_interaction(state: ObjectionHandlerState) -> dict:
    notes = (
        f"Objection: {state['objection']}\n"
        f"Type: {state['objection_type']}\n"
        f"Response: {json.dumps(state['structured_response'])}"
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO interactions (client_id, interaction_type, notes, created_at)
            VALUES (:client_id, 'objection_handled', :notes, now())
            RETURNING id
        """), {"client_id": state["client_id"], "notes": notes[:1000]})
        row = result.fetchone()
        await db.commit()
    return {"interaction_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_objection_handler_agent():
    g = StateGraph(ObjectionHandlerState)
    g.add_node("load_client",        load_client)
    g.add_node("classify_objection", classify_objection)
    g.add_node("generate_response",  generate_response)
    g.add_node("suggest_next_pitch", suggest_next_pitch)
    g.add_node("log_interaction",    log_interaction)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "classify_objection", "error": END})
    g.add_edge("classify_objection", "generate_response")
    g.add_edge("generate_response",  "suggest_next_pitch")
    g.add_edge("suggest_next_pitch", "log_interaction")
    g.add_edge("log_interaction",    END)
    return g.compile()
