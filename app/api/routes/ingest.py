from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.core.config import settings
from app.core.rag import ingest_pdf, sync_policies
from app.core.s3 import put_pdf_bytes
from app.db.postgres import get_db

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest/pdf")
async def ingest_single_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()

    if settings.POLICIES_S3_BUCKET:
        key = f"{settings.POLICIES_S3_PREFIX}{file.filename}" if settings.POLICIES_S3_PREFIX else file.filename
        put_pdf_bytes(key, content)
        # The S3 event notification -> SQS -> consumer pipeline picks this up
        # and ingests it, so there's a single ingestion code path either way.
        return {"filename": file.filename, "status": "uploaded, ingestion pending"}

    save_path = Path(f"data/policies/{file.filename}")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)

    chunks = await ingest_pdf(db, str(save_path), {"source": file.filename})
    return {"filename": file.filename, "chunks_ingested": chunks}


@router.post("/ingest/all")
async def ingest_all(db: AsyncSession = Depends(get_db)):
    total = await sync_policies(db)
    return {"total_chunks_ingested": total}
