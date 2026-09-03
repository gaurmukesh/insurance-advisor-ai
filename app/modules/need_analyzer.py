from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.llm import chat, chat_stream
from app.core.knowledge_graph import format_kg_facts_for_prompt
from app.core.rag import retrieve_context
from app.core.prompt_registry import get_prompt

SYSTEM_PROMPT = """You are an expert insurance advisor assistant in India.
Analyze the client profile and identify insurance gaps.
Be specific, practical, and refer to Indian insurance products (term, health, motor, ULIP, personal accident).
Always mention relevant tax benefits under 80C and 80D where applicable.
If the client has any health conditions (e.g. diabetes, hypertension), explicitly recommend a critical illness rider or standalone critical illness cover.
Format your response clearly with sections."""


async def _build_prompt(db: AsyncSession, client_profile: dict, kg_facts: dict | None = None) -> tuple[str, str]:
    context = await retrieve_context(db, f"insurance for {client_profile.get('goals', 'general')}")

    disposable = (client_profile.get('income') or 0) / 12 - (client_profile.get('liabilities_emi') or 0)

    user_message = f"""
Analyze this client's insurance needs and identify gaps:

Client Profile:
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
- Existing Coverage: {client_profile.get('existing_coverage', 'None mentioned')}

Relevant Policy Context:
{context}

Structured Facts (ground truth from the client's actual owned policies -- trust
these over the generic product descriptions in Relevant Policy Context above
if they conflict):
{format_kg_facts_for_prompt(kg_facts)}

Provide:
1. Current coverage assessment
2. Insurance gaps identified
3. Priority recommendations (high/medium/low)
4. Estimated premium ranges (factoring in disposable income)
5. Tax benefit opportunities under 80C and 80D
"""

    system = await get_prompt("need_analyzer_system") or SYSTEM_PROMPT
    return system, user_message


async def analyze_client_needs(db: AsyncSession, client_profile: dict, kg_facts: dict | None = None) -> str:
    system, user_message = await _build_prompt(db, client_profile, kg_facts)
    return await chat(system, user_message, trace_name="need_analyzer")


async def analyze_client_needs_stream(
    db: AsyncSession, client_profile: dict, kg_facts: dict | None = None
) -> AsyncIterator[str]:
    system, user_message = await _build_prompt(db, client_profile, kg_facts)
    async for chunk in chat_stream(system, user_message, trace_name="need_analyzer_stream"):
        yield chunk
