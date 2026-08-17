import io
import logging
from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.s3 import list_policy_pdf_keys, fetch_pdf_bytes
from app.db.vector_store import insert_chunk, similarity_search, parse_chunk_metadata

logger = logging.getLogger(__name__)


class PdfExtractionError(Exception):
    """PDF bytes could not be parsed -- corrupt file, not a real PDF, etc.
    Raised before any chunk is written, so callers can skip and move on
    without touching the DB."""


async def ingest_pdf_bytes(db: AsyncSession, pdf_bytes: bytes, metadata: dict) -> int:
    source = metadata.get("source", "<unknown>")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise PdfExtractionError(f"failed to extract text from {source}: {e}") from e

    if not full_text.strip():
        # A structurally valid PDF (e.g. scanned images with no text layer, or a
        # blank template) extracts to "" without raising -- treat that the same
        # as a real extraction failure so it retries/DLQs instead of silently
        # "succeeding" with 0 chunks and never surfacing anywhere.
        raise PdfExtractionError(f"{source} contains no extractable text")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(full_text)

    for chunk in chunks:
        await insert_chunk(db, chunk, metadata)

    return len(chunks)


async def ingest_pdf(db: AsyncSession, pdf_path: str, metadata: dict) -> int:
    return await ingest_pdf_bytes(db, Path(pdf_path).read_bytes(), metadata)


async def retrieve_context(db: AsyncSession, query: str, top_k: int = 5) -> str:
    results = await similarity_search(db, query, top_k=top_k)
    if not results:
        return ""
    return "\n\n".join(r["content"] for r in results)


async def get_ingested_sources(db: AsyncSession) -> set[str]:
    result = await db.execute(text("SELECT DISTINCT metadata FROM policy_chunks"))
    return {parse_chunk_metadata(row[0]).get("source") for row in result.fetchall()}


async def sync_policies(db: AsyncSession) -> int:
    """Ingest any policy PDF not yet in policy_chunks. Sources from S3 when
    POLICIES_S3_BUCKET is configured, otherwise from the local data/policies/
    dir. Called at startup, and safe to call again any time as a manual
    reconcile (e.g. via POST /api/v1/ingest/all)."""
    if settings.POLICIES_S3_BUCKET:
        return await sync_policies_from_s3(db)
    return await _sync_policies_from_local_dir(db)


async def _sync_policies_from_local_dir(db: AsyncSession) -> int:
    policies_dir = Path("data/policies")
    if not policies_dir.exists():
        return 0

    ingested_sources = await get_ingested_sources(db)

    total = 0
    for pdf_file in sorted(policies_dir.glob("*.pdf")):
        if pdf_file.name in ingested_sources:
            logger.info(f"RAG sync: already ingested {pdf_file.name}, skipping")
            continue
        logger.info(f"RAG sync: ingesting {pdf_file.name} ...")
        try:
            chunks = await ingest_pdf(db, str(pdf_file), {"source": pdf_file.name})
        except PdfExtractionError as e:
            logger.error(f"RAG sync: {pdf_file.name} could not be read, skipping — {e}")
            await db.rollback()
            continue
        except Exception as e:
            logger.error(f"RAG sync: {pdf_file.name} failed to ingest, skipping — {e}")
            await db.rollback()
            continue
        total += chunks
        logger.info(f"RAG sync: {pdf_file.name} → {chunks} chunks")

    if total:
        logger.info(f"RAG sync complete — {total} new chunks added")
    return total


async def sync_policies_from_s3(db: AsyncSession) -> int:
    """Reconciliation sweep over the configured S3 bucket -- ingests any PDF not
    yet recorded in policy_chunks. Each PDF is isolated in its own try/except:
    a corrupt file or a fetch/embedding failure is logged and skipped rather
    than aborting the batch (or, at startup, crashing the app)."""
    try:
        keys = list_policy_pdf_keys()
    except Exception as e:
        logger.error(f"RAG sync: failed to list S3 bucket {settings.POLICIES_S3_BUCKET!r}: {e}")
        return 0

    ingested_sources = await get_ingested_sources(db)

    total = 0
    for key in keys:
        source_name = key.rsplit("/", 1)[-1]
        if source_name in ingested_sources:
            logger.info(f"RAG sync: already ingested {source_name}, skipping")
            continue
        logger.info(f"RAG sync: ingesting {source_name} from s3://{settings.POLICIES_S3_BUCKET}/{key} ...")
        try:
            pdf_bytes = fetch_pdf_bytes(key)
            chunks = await ingest_pdf_bytes(db, pdf_bytes, {"source": source_name})
        except PdfExtractionError as e:
            logger.error(f"RAG sync: {source_name} could not be read, skipping — {e}")
            await db.rollback()
            continue
        except Exception as e:
            logger.error(f"RAG sync: {source_name} failed to ingest, skipping — {e}")
            await db.rollback()
            continue
        total += chunks
        logger.info(f"RAG sync: {source_name} → {chunks} chunks")

    if total:
        logger.info(f"RAG sync complete — {total} new chunks added")
    return total
