import sentry_sdk
from langfuse import Langfuse
from app.core.config import settings

langfuse: Langfuse | None = None


def init_observability():
    global langfuse

    # Skip Sentry if DSN is missing or still a placeholder value
    if settings.SENTRY_DSN and not settings.SENTRY_DSN.startswith("https://..."):
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.APP_ENV,
            traces_sample_rate=0.2,
        )

    # Skip Langfuse if keys are missing or still placeholders
    if settings.LANGFUSE_SECRET_KEY and not settings.LANGFUSE_SECRET_KEY.startswith("sk-lf-..."):
        langfuse = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )


def get_langfuse() -> Langfuse | None:
    return langfuse
