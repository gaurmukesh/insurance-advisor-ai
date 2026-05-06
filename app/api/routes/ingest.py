from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.db.postgres import get_db
from app.core.rag import ingest_pdf, ingest_all_policies

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest/pdf")
async def ingest_single_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    save_path = Path(f"data/policies/{file.filename}")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    save_path.write_bytes(content)

    chunks = await ingest_pdf(db, str(save_path), {"source": file.filename})
    return {"filename": file.filename, "chunks_ingested": chunks}


@router.post("/ingest/all")
async def ingest_all(db: AsyncSession = Depends(get_db)):
    total = await ingest_all_policies(db)
    return {"total_chunks_ingested": total}
