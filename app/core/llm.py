import time
from typing import AsyncIterator

import openai
import structlog
from app.core.config import settings
from app.core.observability import get_langfuse
from app.core.pii_guard import scrub
from app.core.semantic_cache import get_cached, set_cached

logger = structlog.get_logger("llm")

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def _call(model: str, system_prompt: str, user_message: str, trace_name: str) -> str:
    langfuse = get_langfuse()
    trace = langfuse.trace(name=trace_name) if langfuse else None

    user_message = scrub(user_message)
    start = time.monotonic()

    cached = await get_cached(system_prompt, user_message)
    if cached:
        logger.info(
            "llm_call", trace_name=trace_name, model=model, cache_hit=True,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return cached

    response = await _get_client().chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    output = response.choices[0].message.content

    await set_cached(system_prompt, user_message, output)

    logger.info(
        "llm_call",
        trace_name=trace_name,
        model=model,
        cache_hit=False,
        duration_ms=int((time.monotonic() - start) * 1000),
        tokens_in=response.usage.prompt_tokens,
        tokens_out=response.usage.completion_tokens,
    )

    if trace:
        trace.generation(
            name=trace_name,
            model=model,
            input=user_message,
            output=output,
            usage={
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )

    return output


async def chat(system_prompt: str, user_message: str, trace_name: str = "llm_call") -> str:
    """GPT-4o — for complex tasks: need analysis, product recommendation, RAG."""
    return await _call("gpt-4o", system_prompt, user_message, trace_name)


async def chat_stream(
    system_prompt: str, user_message: str, trace_name: str = "llm_call_stream"
) -> AsyncIterator[str]:
    """Token-by-token variant of chat() for gpt-4o. Same cache: a hit yields the
    cached text as a single chunk instead of re-calling OpenAI."""
    langfuse = get_langfuse()
    trace = langfuse.trace(name=trace_name) if langfuse else None

    user_message = scrub(user_message)

    cached = await get_cached(system_prompt, user_message)
    if cached:
        yield cached
        return

    stream = await _get_client().chat.completions.create(
        model="gpt-4o",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    chunks: list[str] = []
    async for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            chunks.append(delta)
            yield delta

    full_output = "".join(chunks)
    await set_cached(system_prompt, user_message, full_output)

    if trace:
        trace.generation(name=trace_name, model="gpt-4o", input=user_message, output=full_output)


async def chat_mini(system_prompt: str, user_message: str, trace_name: str = "llm_call_mini") -> str:
    """GPT-4o mini — for simple tasks: email drafting, follow-ups."""
    return await _call("gpt-4o-mini", system_prompt, user_message, trace_name)
