from sqlalchemy.ext.asyncio import AsyncSession
from app.core.llm import chat
from app.core.rag import retrieve_context

SYSTEM_PROMPT = """You are an expert insurance advisor assistant in India.
Analyze the client profile and identify insurance gaps.
Be specific, practical, and refer to Indian insurance products (term, health, motor, ULIP, personal accident).
Always mention relevant tax benefits under 80C and 80D where applicable.
Format your response clearly with sections."""


async def analyze_client_needs(db: AsyncSession, client_profile: dict) -> str:
    context = await retrieve_context(db, f"insurance for {client_profile.get('goals', 'general')}")

    user_message = f"""
Analyze this client's insurance needs and identify gaps:

Client Profile:
- Name: {client_profile.get('name')}
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}
- Existing Policies: {client_profile.get('existing_policies', 'None mentioned')}

Relevant Policy Context:
{context}

Provide:
1. Current coverage assessment
2. Insurance gaps identified
3. Priority recommendations (high/medium/low)
4. Estimated premium ranges
5. Tax benefit opportunities
"""

    return await chat(SYSTEM_PROMPT, user_message, trace_name="need_analyzer")
