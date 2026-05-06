from sqlalchemy.ext.asyncio import AsyncSession
from app.core.llm import chat
from app.core.rag import retrieve_context

SYSTEM_PROMPT = """You are an expert insurance product advisor in India.
Recommend the top 3 most suitable insurance products for the client.
Base recommendations on their profile and available policy details.
Always provide a comparison table and clear reasoning.
Mention premium estimates, sum assured, and key features."""


async def recommend_products(db: AsyncSession, client_profile: dict, need_analysis: str) -> str:
    query = f"{client_profile.get('goals', '')} insurance {client_profile.get('risk_appetite', '')} risk"
    context = await retrieve_context(db, query, top_k=6)

    user_message = f"""
Recommend top 3 insurance products for this client:

Client Profile:
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}

Need Analysis Summary:
{need_analysis[:500]}

Available Policy Information:
{context}

Provide:
1. Top 3 product recommendations with insurer names
2. Comparison table (product, premium, sum assured, key benefit)
3. Why each product suits this client
4. Which one to pitch first and why
"""

    return await chat(SYSTEM_PROMPT, user_message, trace_name="product_recommender")
