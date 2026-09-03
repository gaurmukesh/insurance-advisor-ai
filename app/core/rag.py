import asyncio
import io
import logging
from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.product_extraction import extract_and_store_product_kg
from app.core.s3 import list_policy_pdf_keys, fetch_pdf_bytes
from app.db.vector_store import insert_chunk, similarity_search, parse_chunk_metadata

logger = logging.getLogger(__name__)


class PdfExtractionError(Exception):
    """PDF bytes could not be parsed -- corrupt file, not a real PDF, etc.
    Raised before any chunk is written, so callers can skip and move on
    without touching the DB."""


# Markers that indicate a PDF is a named individual's *issued* policy (e.g.
# data/policies/insurance_policy.pdf: "Full Name Amit Singh", "Policy Holder
# ID PH-2024-78421", an "INSURED MEMBERS" table with DOBs) rather than a
# generic per-product spec sheet ("Coverage Summary" / "Key Exclusions"
# templates like the other sample PDFs). Running the former through
# structured extraction would both mint a bogus one-off "product" row and
# risk sending personal details through the extraction LLM call.
_ISSUED_POLICY_MARKERS = ("policyholder details", "policy holder id", "insured members", "date of birth")


def _looks_like_product_template(full_text: str) -> bool:
    """False negatives (skipping a real template) just fall back to today's
    vector-only behavior, so this errs toward skipping when unsure."""
    lowered = full_text.lower()
    return not any(marker in lowered for marker in _ISSUED_POLICY_MARKERS)


def _extract_chunks_and_text(pdf_bytes: bytes, source: str) -> tuple[str, list[str]]:
    """CPU-bound PDF parsing and splitting -- run via asyncio.to_thread so it
    doesn't block the event loop (and everything else sharing it, e.g. HTTP
    request handling) for the duration of a large PDF."""
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
    return full_text, splitter.split_text(full_text)


async def ingest_pdf_bytes(db: AsyncSession, pdf_bytes: bytes, metadata: dict) -> int:
    source = metadata.get("source", "<unknown>")
    full_text, chunks = await asyncio.to_thread(_extract_chunks_and_text, pdf_bytes, source)

    for chunk in chunks:
        await insert_chunk(db, chunk, metadata)

    if _looks_like_product_template(full_text):
        try:
            # A failure here must not poison the whole transaction -- without
            # a SAVEPOINT, a DB-level error during extraction (e.g. a bad
            # value on flush) aborts the entire transaction at the Postgres
            # level, taking the chunk inserts above down with it even though
            # they already succeeded. begin_nested() scopes the rollback to
            # just this block.
            async with db.begin_nested():
                await extract_and_store_product_kg(db, full_text, source)
        except Exception as e:
            # A broken extraction must never roll back the chunks above --
            # vector search should keep working even if structured KG
            # extraction fails.
            logger.error(f"RAG ingest: product KG extraction failed for {source}, chunks still committed — {e}")
    else:
        logger.info(f"RAG ingest: {source} looks like an issued policy document, not a product template — skipping KG extraction")

    # Commit once, after every chunk is inserted, so a crash or exception
    # partway through a large PDF leaves nothing committed -- the caller's
    # rollback discards the whole attempt instead of leaving a partial set
    # of chunks that later reads as "already ingested" and never retries.
    await db.commit()

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
