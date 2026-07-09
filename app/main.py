import time
import uuid

import openai
import structlog
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.logging import configure_logging
from app.core.observability import init_observability
from app.core.rag import sync_policies
from app.db.postgres import init_db, AsyncSessionLocal
from app.api.routes import clients, recommendations, emails, ingest, advisors, whatsapp, pitch, documents, metrics, agents, approvals, auth
from app.mcp.server import mcp
from fastapi.middleware.cors import CORSMiddleware
import os

# Import all models so Base.metadata knows every table before create_all runs.
import app.models.advisor  # noqa: F401
import app.models.client  # noqa: F401
import app.models.policy  # noqa: F401
import app.models.email_log  # noqa: F401
import app.models.interaction  # noqa: F401
import app.models.whatsapp_log  # noqa: F401
from app.scheduler.premium_reminder import run_premium_reminder_job
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
configure_logging()
request_logger = structlog.get_logger("http")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    await init_db()
    logger.info("Database initialized")

    async with AsyncSessionLocal() as db:
        try:
            new_chunks = await sync_policies(db)
            if new_chunks:
                logger.info(f"RAG sync: {new_chunks} new chunks ingested from data/policies/")
        except (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as e:
            # OpenAI outage shouldn't take the whole app down — skip ingestion for
            # now, it'll pick up any un-ingested PDFs on the next restart.
            logger.error(f"RAG sync skipped — OpenAI unavailable at startup: {e}")

    scheduler.add_job(run_premium_reminder_job, "cron", hour=8, minute=0)
    scheduler.start()
    logger.info("Scheduler started — premium reminders run daily at 8:00 AM")

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Insurance Advisor AI",
    description="AI assistant for insurance advisors",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    response.headers["X-Request-ID"] = trace_id
    request_logger.info(
        "request_complete",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


async def _openai_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    request_logger.error("openai_unavailable", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "AI service is temporarily unavailable. Please try again shortly."},
    )


app.add_exception_handler(openai.APIConnectionError, _openai_unavailable_handler)
app.add_exception_handler(openai.RateLimitError, _openai_unavailable_handler)
app.add_exception_handler(openai.InternalServerError, _openai_unavailable_handler)

app.include_router(auth.router)
app.include_router(advisors.router)
app.include_router(clients.router)
app.include_router(recommendations.router)
app.include_router(emails.router)
app.include_router(ingest.router)
app.include_router(whatsapp.router)
app.include_router(pitch.router)
app.include_router(documents.router)
app.include_router(metrics.router)
app.include_router(agents.router)
app.include_router(approvals.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.mount("/mcp", mcp.sse_app())
