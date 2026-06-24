import json
from app.core.llm import chat

PITCH_SYSTEM_PROMPT = """You are an expert insurance sales coach in India.
Generate a personalized sales pitch for an insurance advisor to use with their client.
Be conversational, empathetic, and specific to the client's profile.
Focus on real needs, not just products. Avoid jargon.
Format: Opening → Key Need → Recommended Solution → Call to Action."""

OBJECTION_SYSTEM_PROMPT = """You are an expert insurance sales coach in India.
Help an insurance advisor deliver a strong, detailed response to a client objection.
You MUST respond with valid JSON only — no markdown, no text outside the JSON.
Return exactly this structure:
{
  "acknowledge": "1-2 sentences that genuinely validate the client's concern without being dismissive",
  "reframe": "1-2 sentences that reframe the objection into an opportunity or a different perspective",
  "strong_reason": "2-3 sentences — the core compelling argument for why they need insurance NOW, not later",
  "client_specific_impact": "2-3 sentences — use the client's exact age, income, family, health to make it personal",
  "stat_or_fact": "one real IRDAI statistic, claim data, or insurance fact that backs the argument",
  "closing_line": "one confident, non-pushy line to move toward a decision"
}"""

COMMON_OBJECTIONS = [
    "premium is too high",
    "I already have insurance",
    "I will think about it",
    "I don't trust insurance companies",
    "I am young and healthy, I don't need it",
    "I don't have time right now",
    "my employer already covers me",
]


async def generate_pitch(client_profile: dict) -> str:
    disposable = (client_profile.get('income') or 0) / 12 - (client_profile.get('liabilities_emi') or 0)

    user_message = f"""
Generate a sales pitch for the following client:

- Name: {client_profile.get('name')}
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Monthly Disposable (after EMI): ₹{disposable:,.0f}
- Family Size: {client_profile.get('family_size')}
- Dependents: {client_profile.get('dependents_detail', 'None')}
- Employment Type: {client_profile.get('employment_type', 'Not specified')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}
- City Tier: {client_profile.get('city_tier', 'Not specified')}
- Health Conditions: {client_profile.get('health_conditions', 'None')}
- Existing Coverage: {client_profile.get('existing_coverage', 'None')}

Create a natural, personalized pitch the advisor can use in a conversation.
"""
    return await chat(PITCH_SYSTEM_PROMPT, user_message, trace_name="pitch_generator")


async def handle_objection(objection: str, client_profile: dict) -> dict:
    disposable = (client_profile.get('income') or 0) / 12 - (client_profile.get('liabilities_emi') or 0)

    user_message = f"""
Client objection: "{objection}"

Client context:
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Monthly Disposable (after EMI): ₹{disposable:,.0f}
- Employment Type: {client_profile.get('employment_type', 'Not specified')}
- Family Size: {client_profile.get('family_size')}
- Goals: {client_profile.get('goals')}
- Health Conditions: {client_profile.get('health_conditions', 'None')}
- Existing Coverage: {client_profile.get('existing_policies', 'None')}

Return JSON only. Make client_specific_impact reference their exact profile details.
"""
    raw = await chat(OBJECTION_SYSTEM_PROMPT, user_message, trace_name="objection_handler")

    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return {"acknowledge": raw, "reframe": "", "strong_reason": "",
                "client_specific_impact": "", "stat_or_fact": "", "closing_line": ""}
