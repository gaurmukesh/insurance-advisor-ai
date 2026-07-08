"""
Re-ingests all PDFs from data/policies/ into the vector store.
Clears existing policy_chunks first so there are no stale embeddings.
Run from project root: python scripts/reingest_policies.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal, init_db
from app.core.rag import ingest_pdf


async def main():
    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM policy_chunks"))
        before = result.scalar()
        print(f"Existing chunks in DB: {before}")

        print("Clearing all existing policy_chunks...")
        await db.execute(text("TRUNCATE TABLE policy_chunks RESTART IDENTITY"))
        await db.commit()
        print("Cleared.")

    policies_dir = Path("data/policies")
    pdf_files = sorted(policies_dir.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF(s) to ingest:\n")

    total = 0
    async with AsyncSessionLocal() as db:
        for pdf in pdf_files:
            print(f"  Ingesting: {pdf.name} ...", end=" ", flush=True)
            try:
                chunks = await ingest_pdf(db, str(pdf), {"source": pdf.name})
                total += chunks
                print(f"{chunks} chunks")
            except Exception as e:
                print(f"FAILED — {e}")

    print(f"\nDone. Total chunks ingested: {total}")

    try:
        async with AsyncSessionLocal() as db:
            # metadata is stored as JSON (see insert_chunk) — rows written before
            # that fix used a Python dict repr instead, so this cast can still
            # fail on old, not-yet-reingested rows; the try/except keeps this
            # summary purely informational either way.
            result = await db.execute(text(
                "SELECT metadata::json->>'source' as source_file, COUNT(*) as chunks "
                "FROM policy_chunks GROUP BY source_file ORDER BY source_file"
            ))
            rows = result.fetchall()
            print("\nChunks per document:")
            for row in rows:
                print(f"  {row.source_file}: {row.chunks} chunks")
    except Exception as e:
        # Purely informational summary — never fail the run over it.
        print(f"\n(could not print per-document summary: {e})")


asyncio.run(main())
