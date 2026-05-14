from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.observability import init_observability
from app.db.postgres import init_db
from app.api.routes import clients, recommendations, emails, ingest, advisors, whatsapp, pitch
from fastapi.middleware.cors import CORSMiddleware

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

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    await init_db()
    logger.info("Database initialized")

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
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advisors.router)
app.include_router(clients.router)
app.include_router(recommendations.router)
app.include_router(emails.router)
app.include_router(ingest.router)
app.include_router(whatsapp.router)
app.include_router(pitch.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
