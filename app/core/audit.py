import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def log_ai_decision(
    db: AsyncSession,
    trace_name: str,
    input_text: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    client_id: str = None,
    advisor_id: str = None,
    outcome: str = "success",
):
    """
    Write an immutable record of every AI decision.
    Stores SHA-256 of the input (not the input itself) for tamper-evidence.
    """
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()
    await db.execute(text("""
        INSERT INTO ai_audit_log
            (trace_name, client_id, advisor_id, input_hash,
             model, tokens_in, tokens_out, latency_ms, outcome)
        VALUES
            (:trace_name, :client_id, :advisor_id, :input_hash,
             :model, :tokens_in, :tokens_out, :latency_ms, :outcome)
    """), {
        "trace_name": trace_name, "client_id": client_id,
        "advisor_id": advisor_id, "input_hash": input_hash,
        "model": model, "tokens_in": tokens_in,
        "tokens_out": tokens_out, "latency_ms": latency_ms,
        "outcome": outcome,
    })
    await db.commit()
