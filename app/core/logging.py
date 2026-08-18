import logging

import structlog

from app.core.config import settings

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.APP_ENV == "production"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configure_cloudwatch_handler()


def _configure_cloudwatch_handler() -> None:
    """Mirror stdlib log records (e.g. app.workers.s3_ingest_consumer's "SQS
    ingest: ..." lines) into CloudWatch Logs, in addition to stdout. structlog
    uses PrintLoggerFactory and bypasses stdlib logging entirely, so this only
    covers modules that log via logging.getLogger(__name__) -- which is what
    the ingestion pipeline uses. No-op when CLOUDWATCH_LOG_GROUP is unset, so
    local/dev/CI runs never need AWS credentials for this."""
    if not settings.CLOUDWATCH_LOG_GROUP:
        return

    import boto3
    import watchtower

    logs_client = boto3.client("logs", region_name=settings.AWS_REGION or None)
    handler = watchtower.CloudWatchLogHandler(
        log_group_name=settings.CLOUDWATCH_LOG_GROUP,
        boto3_client=logs_client,
        send_interval=10,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logger.info(f"CloudWatch log handler attached — group {settings.CLOUDWATCH_LOG_GROUP}")
