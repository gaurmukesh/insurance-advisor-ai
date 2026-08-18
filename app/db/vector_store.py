import ast
import json

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.semantic_cache import get_cached_value, set_cached_value
import openai

_openai_client: openai.AsyncOpenAI | None = None

_EMBEDDING_MODEL = "text-embedding-3-small"


def _get_openai_client() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        # Fail fast if OpenAI is unreachable (5s connect); embeddings are small
        # single-shot calls so 20s read is generous. max_retries backs off on
        # transient connection/rate-limit/5xx errors.
        _openai_client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=httpx.Timeout(20.0, connect=5.0),
            max_retries=3,
        )
    return _openai_client


async def get_embedding(text_input: str) -> list[float]:
    cache_key = f"{_EMBEDDING_MODEL}:{text_input}"
    cached = await get_cached_value("embedding", cache_key)
    if cached:
        return json.loads(cached)

    response = await _get_openai_client().embeddings.create(
        model=_EMBEDDING_MODEL,
        input=text_input,
    )
    embedding = response.data[0].embedding

    await set_cached_value("embedding", cache_key, json.dumps(embedding), ttl=86400)
    return embedding


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
        {"content": content, "metadata": json.dumps(metadata), "embedding": embedding_str},
    )


def parse_chunk_metadata(raw: str) -> dict:
    """policy_chunks.metadata is stored as JSON going forward, but rows written
    before this fix used Python's str(dict) repr (single-quoted, not valid
    JSON) — fall back to literal_eval so old rows still parse instead of
    silently failing dedup/citation lookups until they're re-ingested."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return {}
