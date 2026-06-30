import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.llm import chat
from app.core.rag import retrieve_context
from app.core.guardrails import validate_output

SYSTEM_PROMPT = """You are an expert insurance product advisor in India.
Recommend the top 3 most suitable insurance products for the client.
Never use IRDAI-prohibited phrases such as 'guaranteed returns', 'no risk',
'risk-free', '100% safe investment', 'assured profit', or 'tax-free guaranteed'.
You MUST respond with valid JSON only — no markdown, no explanation outside the JSON.
Return exactly this structure:
[
  {
    "rank": 1,
    "product_name": "...",
    "insurer": "...",
    "type": "term|health|ulip|personal_accident|motor|other",
    "premium_per_month": <number in ₹>,
    "sum_assured": "...",
    "key_benefit": "one sentence",
    "why_suits": "2-3 sentences specific to this client's profile",
    "tax_benefit": "e.g. 80C / 80D / none",
    "pitch_first": true or false
  }
]
Only one product should have pitch_first=true."""


async def recommend_products(db: AsyncSession, client_profile: dict, need_analysis: str) -> list[dict]:
    query = f"{client_profile.get('goals', '')} insurance {client_profile.get('risk_appetite', '')} risk"
    context = await retrieve_context(db, query, top_k=6)

    disposable = (client_profile.get('income') or 0) / 12 - (client_profile.get('liabilities_emi') or 0)

    user_message = f"""
Recommend top 3 insurance products for this client. Return JSON only.

Client Profile:
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

Need Analysis Summary:
{need_analysis[:500]}

Available Policy Information:
{context}
"""

    raw = await chat(SYSTEM_PROMPT, user_message, trace_name="product_recommender")
    validate_output(raw, context="product_recommender")

    try:
        # strip markdown code fences if the model adds them
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        # fallback: return as a single plain-text card so the UI never breaks
        return [{"rank": 1, "product_name": "Recommendation", "insurer": "", "type": "other",
                 "premium_per_month": 0, "sum_assured": "", "key_benefit": raw,
                 "why_suits": "", "tax_benefit": "", "pitch_first": True}]
