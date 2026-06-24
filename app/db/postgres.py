from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_db_with_advisor(request: Request) -> AsyncSession:
    """Use instead of get_db for RLS-protected endpoints.
    Sets app.current_advisor_id so Postgres enforces advisor isolation at query time."""
    advisor_id = request.headers.get("X-Advisor-ID", "")
    async with AsyncSessionLocal() as session:
        if advisor_id:
            await session.execute(
                text("SET LOCAL app.current_advisor_id = :aid"),
                {"aid": advisor_id},
            )
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
