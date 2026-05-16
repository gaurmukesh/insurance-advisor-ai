from pypdf import PdfReader
from app.core.llm import chat

SYSTEM_PROMPT = """You are an expert insurance document analyst in India.
Analyze the provided policy document and give a clear, structured summary.
Use plain language that an advisor can explain to a client.
Always structure your response with these sections:
1. Key Highlights
2. What's Covered
3. Exclusions (What's NOT Covered)
4. Claim Process
5. Tax Benefits (if any)
6. Advisor's Tip"""

COMPARE_SYSTEM_PROMPT = """You are an expert insurance document analyst in India.
Compare the two provided policy documents and give a clear, structured comparison.
Use plain language. Structure your response with:
1. Quick Summary of Each Policy
2. Side-by-Side Comparison Table (coverage, premium, sum assured, exclusions, claim process)
3. Which Policy Is Better For Whom
4. Advisor's Recommendation"""


def _extract_text(pdf_bytes: bytes) -> str:
    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text[:12000]  # GPT-4o context window guard


async def summarize_document(pdf_bytes: bytes, filename: str) -> str:
    text = _extract_text(pdf_bytes)
    if not text.strip():
        return "Could not extract text from this PDF. It may be a scanned image-based document."

    user_message = f"""Analyze this insurance policy document and provide a structured summary.

Filename: {filename}

Document Content:
{text}
"""
    return await chat(SYSTEM_PROMPT, user_message, trace_name="doc_assistant_summarize")


async def compare_documents(pdf_bytes_a: bytes, filename_a: str, pdf_bytes_b: bytes, filename_b: str) -> str:
    text_a = _extract_text(pdf_bytes_a)
    text_b = _extract_text(pdf_bytes_b)

    user_message = f"""Compare these two insurance policy documents.

=== Document 1: {filename_a} ===
{text_a}

=== Document 2: {filename_b} ===
{text_b}
"""
    return await chat(COMPARE_SYSTEM_PROMPT, user_message, trace_name="doc_assistant_compare")
