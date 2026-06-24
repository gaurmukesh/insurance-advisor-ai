from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

_cache: dict[str, str] = {}


async def get_prompt(name: str) -> str | None:
    """
    Fetch the active version of a named prompt from the registry.
    Returns None if not found — caller falls back to hardcoded default.
    """
    if name in _cache:
        return _cache[name]

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("""
                SELECT content FROM prompt_registry
                WHERE name = :name AND is_active = true
                LIMIT 1
            """),
            {"name": name},
        )).fetchone()

    if row:
        _cache[name] = row.content
        return row.content
    return None


def invalidate_cache(name: str = None):
    """Call after promoting a new prompt version to active."""
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()
