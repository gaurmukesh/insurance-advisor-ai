from fastapi import APIRouter, UploadFile, File, HTTPException
from app.modules.doc_assistant import summarize_document, compare_documents

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/document-summary")
async def summarize(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    pdf_bytes = await file.read()
    summary = await summarize_document(pdf_bytes, file.filename)
    return {"filename": file.filename, "summary": summary}


@router.post("/document-compare")
async def compare(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    for f in (file_a, file_b):
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
    bytes_a = await file_a.read()
    bytes_b = await file_b.read()
    result = await compare_documents(bytes_a, file_a.filename, bytes_b, file_b.filename)
    return {"file_a": file_a.filename, "file_b": file_b.filename, "comparison": result}
