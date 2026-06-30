from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
import openai

_openai_client: openai.AsyncOpenAI | None = None


def _get_openai_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def get_embedding(text_input: str) -> list[float]:
    response = await _get_openai_client().embeddings.create(
        model="text-embedding-3-small",
        input=text_input,
    )
    return response.data[0].embedding


async def similarity_search(db: AsyncSession, query: str, top_k: int = 5) -> list[dict]:
    query_embedding = await get_embedding(query)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = await db.execute(
        text("""
            SELECT content, metadata, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM policy_chunks
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {"embedding": embedding_str, "top_k": top_k},
    )
    rows = result.fetchall()
    return [{"content": r.content, "metadata": r.metadata, "similarity": r.similarity} for r in rows]


async def insert_chunk(db: AsyncSession, content: str, metadata: dict):
    embedding = await get_embedding(content)
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    await db.execute(
        text("""
            INSERT INTO policy_chunks (content, metadata, embedding)
            VALUES (:content, :metadata, CAST(:embedding AS vector))
        """),
        {"content": content, "metadata": str(metadata), "embedding": embedding_str},
    )
    await db.commit()
