import json
import operator
from datetime import date, timedelta
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.models.policy import Policy
from app.modules.email_generator import generate_premium_reminder_email
from app.core.llm import chat


class RenewalAgentState(TypedDict):
    advisor_id: str
    days_ahead: int
    renewals: list[dict]
    scored_renewals: list[dict]
    priority_renewals: list[dict]
    draft_messages: list[dict]
    approval_ids: list[str]
    errors: Annotated[list[str], operator.add]


async def load_renewals(state: RenewalAgentState) -> dict:
    today = date.today()
    until = today + timedelta(days=state.get("days_ahead", 30))
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Policy, Client)
            .join(Client, Policy.client_id == Client.id)
            .where(Client.advisor_id == state["advisor_id"])
            .where(Policy.next_due_date >= today)
            .where(Policy.next_due_date <= until)
            .order_by(Policy.next_due_date)
        )).all()
    if not rows:
        return {"errors": ["No upcoming renewals found"], "renewals": []}
    return {"renewals": [{
        "policy_id": p.id, "policy_no": p.policy_no,
        "product_name": p.product_name, "insurer_name": p.insurer_name,
        "premium_amount": p.premium_amount, "next_due_date": str(p.next_due_date),
        "days_until_due": (p.next_due_date - today).days,
        "client_id": c.id, "client_name": c.name, "client_email": c.email,
        "client_phone": c.phone, "client_status": c.status,
        "client_income": c.income or 0,
    } for p, c in rows]}


async def score_risk(state: RenewalAgentState) -> dict:
    prompt = f"""Score each policy renewal by lapse risk 0–100 (higher = more likely to lapse).
Factors: days_until_due (fewer = higher urgency), premium_amount vs client_income,
client_status ('new' or 'contacted' = less trust built = higher risk).
Add "lapse_risk_score" (int) and "risk_reason" (str) to each item.
Return the same JSON array with these two fields added.

Renewals:
{json.dumps(state['renewals'][:20], default=str)}"""
    raw = await chat(
        "Risk analyst. Score insurance renewal lapse risk. Return JSON only.",
        prompt, trace_name="score_risk"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        scored = json.loads(clean)
    except Exception:
        scored = state["renewals"]
        for i, r in enumerate(sorted(scored, key=lambda x: x["days_until_due"])):
            r["lapse_risk_score"] = max(10, 90 - i * 8)
            r["risk_reason"] = f"{r['days_until_due']} days until due"
    return {"scored_renewals": scored}


async def filter_priority(state: RenewalAgentState) -> dict:
    priority = sorted(
        [r for r in state["scored_renewals"] if r.get("lapse_risk_score", 0) >= 40],
        key=lambda r: r.get("lapse_risk_score", 0), reverse=True
    )[:10]
    return {"priority_renewals": priority}


async def draft_outreach(state: RenewalAgentState) -> dict:
    drafts = []
    for r in state["priority_renewals"]:
        email = await generate_premium_reminder_email(
            client_name=r["client_name"], policy_no=r["policy_no"],
            product_name=r["product_name"], insurer_name=r["insurer_name"],
            premium_amount=r["premium_amount"], due_date=r["next_due_date"],
            advisor_name="Your Advisor",
        )
        drafts.append({
            "client_id": r["client_id"], "client_name": r["client_name"],
            "client_email": r["client_email"], "policy_no": r["policy_no"],
            "lapse_risk_score": r.get("lapse_risk_score"),
            "risk_reason": r.get("risk_reason", ""),
            "email": email,
            "whatsapp_text": (
                f"Hi {r['client_name']}, your {r['product_name']} premium of "
                f"₹{r['premium_amount']:,.0f} is due on {r['next_due_date']}. "
                f"Please renew to keep your coverage active."
            ),
        })
    return {"draft_messages": drafts}


async def queue_approval(state: RenewalAgentState) -> dict:
    ids = []
    async with AsyncSessionLocal() as db:
        for draft in state["draft_messages"]:
            result = await db.execute(text("""
                INSERT INTO approval_queue
                    (client_id, advisor_id, action_type, payload, status, created_at)
                VALUES (:client_id, :advisor_id, 'send_renewal_reminder', :payload, 'pending', now())
                RETURNING id
            """), {
                "client_id": draft["client_id"],
                "advisor_id": state["advisor_id"],
                "payload": json.dumps(draft, default=str),
            })
            row = result.fetchone()
            if row:
                ids.append(str(row.id))
        await db.commit()
    return {"approval_ids": ids}


async def notify_advisor(state: RenewalAgentState) -> dict:
    print(f"[Renewals Agent] {len(state['approval_ids'])} items queued for {state['advisor_id']}")
    return {}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def _check_priority(state) -> str:
    return "no_priority" if not state.get("priority_renewals") else "continue"


def build_renewals_agent():
    g = StateGraph(RenewalAgentState)
    g.add_node("load_renewals",   load_renewals)
    g.add_node("score_risk",      score_risk)
    g.add_node("filter_priority", filter_priority)
    g.add_node("draft_outreach",  draft_outreach)
    g.add_node("queue_approval",  queue_approval)
    g.add_node("notify_advisor",  notify_advisor)
    g.set_entry_point("load_renewals")
    g.add_conditional_edges("load_renewals", _check_errors,
                            {"continue": "score_risk", "error": END})
    g.add_edge("score_risk",      "filter_priority")
    g.add_conditional_edges("filter_priority", _check_priority,
                            {"continue": "draft_outreach", "no_priority": END})
    g.add_edge("draft_outreach",  "queue_approval")
    g.add_edge("queue_approval",  "notify_advisor")
    g.add_edge("notify_advisor",  END)
    return g.compile()
