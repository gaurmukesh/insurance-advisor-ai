import asyncio
import json
import logging
import urllib.parse

import boto3

from app.core.config import settings
from app.core.rag import PdfExtractionError, get_ingested_sources, ingest_pdf_bytes
from app.core.s3 import fetch_pdf_bytes
from app.db.postgres import AsyncSessionLocal

logger = logging.getLogger(__name__)

_sqs_client = None


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs", region_name=settings.AWS_REGION or None)
    return _sqs_client


def _extract_pdf_keys(message_body: str) -> list[str]:
    """S3-to-SQS event notification bodies look like {"Records": [{"eventName":
    "ObjectCreated:Put", "s3": {"object": {"key": "..."}}}]}. S3 URL-encodes
    keys in event payloads (e.g. spaces become '+')."""
    try:
        payload = json.loads(message_body)
    except json.JSONDecodeError:
        return []

    keys = []
    for record in payload.get("Records", []):
        if not record.get("eventName", "").startswith("ObjectCreated"):
            continue
        raw_key = record.get("s3", {}).get("object", {}).get("key")
        if raw_key and raw_key.lower().endswith(".pdf"):
            keys.append(urllib.parse.unquote_plus(raw_key))
    return keys


async def _handle_message(message: dict) -> None:
    """Ingest every PDF referenced by one SQS message. Raises on failure so
    the caller leaves the message undeleted -- SQS's redrive policy retries
    it, and eventually parks a permanently-bad message in the DLQ, without
    affecting any other message in flight."""
    keys = _extract_pdf_keys(message["Body"])
    if not keys:
        return

    async with AsyncSessionLocal() as db:
        ingested_sources = await get_ingested_sources(db)
        for key in keys:
            source_name = key.rsplit("/", 1)[-1]
            if source_name in ingested_sources:
                logger.info(f"SQS ingest: already ingested {source_name}, skipping")
                continue
            logger.info(f"SQS ingest: ingesting {source_name} from s3://{settings.POLICIES_S3_BUCKET}/{key} ...")
            try:
                pdf_bytes = await asyncio.to_thread(fetch_pdf_bytes, key)
                chunks = await ingest_pdf_bytes(db, pdf_bytes, {"source": source_name})
            except PdfExtractionError as e:
                logger.error(f"SQS ingest: {source_name} could not be read, will retry/DLQ — {e}")
                await db.rollback()
                raise
            except Exception as e:
                logger.error(f"SQS ingest: {source_name} failed to ingest, will retry/DLQ — {e}")
                await db.rollback()
                raise
            logger.info(f"SQS ingest: {source_name} → {chunks} chunks")


async def run_sqs_consumer() -> None:
    """Long-polls the policies-ingest queue and ingests each new PDF as it
    lands in S3. Runs for the lifetime of the app; cancelled on shutdown."""
    client = _get_sqs_client()
    logger.info(f"SQS ingest consumer starting — polling {settings.POLICIES_SQS_QUEUE_URL}")

    while True:
        try:
            response = await asyncio.to_thread(
                client.receive_message,
                QueueUrl=settings.POLICIES_SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
            )
        except Exception as e:
            logger.error(f"SQS ingest: receive_message failed, retrying in 5s — {e}")
            await asyncio.sleep(5)
            continue

        for message in response.get("Messages", []):
            try:
                await _handle_message(message)
            except Exception:
                # Left undeleted: SQS redelivers after the visibility timeout
                # expires, up to the queue's RedrivePolicy maxReceiveCount
                # before moving the message to the DLQ.
                continue

            try:
                await asyncio.to_thread(
                    client.delete_message,
                    QueueUrl=settings.POLICIES_SQS_QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"],
                )
            except Exception as e:
                logger.error(f"SQS ingest: failed to delete message after successful ingest — {e}")
