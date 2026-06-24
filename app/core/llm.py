import openai
from app.core.config import settings
from app.core.observability import get_langfuse
from app.core.pii_guard import scrub
from app.core.semantic_cache import get_cached, set_cached

client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def _call(model: str, system_prompt: str, user_message: str, trace_name: str) -> str:
    langfuse = get_langfuse()
    trace = langfuse.trace(name=trace_name) if langfuse else None

    user_message = scrub(user_message)

    cached = await get_cached(system_prompt, user_message)
    if cached:
        return cached

    response = await client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )

    output = response.choices[0].message.content

    await set_cached(system_prompt, user_message, output)

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


async def chat_mini(system_prompt: str, user_message: str, trace_name: str = "llm_call_mini") -> str:
    """GPT-4o mini — for simple tasks: email drafting, follow-ups."""
    return await _call("gpt-4o-mini", system_prompt, user_message, trace_name)
