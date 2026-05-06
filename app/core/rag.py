from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.vector_store import insert_chunk, similarity_search


async def ingest_pdf(db: AsyncSession, pdf_path: str, metadata: dict):
    reader = PdfReader(pdf_path)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(full_text)

    for chunk in chunks:
        await insert_chunk(db, chunk, metadata)

    return len(chunks)


async def retrieve_context(db: AsyncSession, query: str, top_k: int = 5) -> str:
    results = await similarity_search(db, query, top_k=top_k)
    if not results:
        return ""
    return "\n\n".join(r["content"] for r in results)


async def ingest_all_policies(db: AsyncSession):
    policies_dir = Path("data/policies")
    count = 0
    for pdf_file in policies_dir.glob("*.pdf"):
        chunks = await ingest_pdf(db, str(pdf_file), {"source": pdf_file.name})
        count += chunks
    return count
