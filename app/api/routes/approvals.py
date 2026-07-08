import json
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_advisor
from app.api.routes.emails import send_email
from app.db.postgres import get_db
from app.models.advisor import Advisor
from app.models.email_log import EmailLog

router = APIRouter(prefix="/api/v1/approval-queue", tags=["approvals"])


def _require_uuid(item_id: str) -> None:
    try:
        uuid_mod.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Item not found")


@router.get("")
async def list_approvals(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    rows = (await db.execute(text("""
        SELECT aq.id, aq.client_id, aq.advisor_id, aq.action_type,
               aq.payload, aq.status, aq.created_at,
               c.name AS client_name, c.email AS client_email
        FROM approval_queue aq
        LEFT JOIN clients c ON aq.client_id = c.id
        WHERE aq.advisor_id = :advisor_id AND aq.status = :status
        ORDER BY aq.created_at DESC
    """), {"advisor_id": current.id, "status": status})).fetchall()

    result = []
    for row in rows:
        payload = json.loads(row.payload)
        email = payload.get("email", {})
        result.append({
            "id": str(row.id),
            "client_id": row.client_id,
            "client_name": row.client_name or payload.get("client_name", "Unknown"),
            "client_email": row.client_email or payload.get("client_email"),
            "action_type": row.action_type,
            "status": row.status,
            "created_at": str(row.created_at),
            "email_subject": email.get("subject", ""),
            "email_body": email.get("body", ""),
            "lapse_risk_score": payload.get("lapse_risk_score"),
            "risk_reason": payload.get("risk_reason"),
            "gaps": payload.get("gaps", []),
            "recommendations": payload.get("recommendations", []),
        })
    return result


async def _fetch_own_item(db: AsyncSession, item_id: str, advisor_id: str):
    row = (await db.execute(text("""
        SELECT aq.id, aq.client_id, aq.advisor_id, aq.action_type, aq.payload, aq.status,
               c.name AS client_name, c.email AS client_email
        FROM approval_queue aq
        LEFT JOIN clients c ON aq.client_id = c.id
        WHERE aq.id = :id
    """), {"id": item_id})).fetchone()
    if not row or row.advisor_id != advisor_id:
        raise HTTPException(status_code=404, detail="Item not found")
    return row


@router.post("/{item_id}/approve")
async def approve_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    _require_uuid(item_id)
    row = await _fetch_own_item(db, item_id, current.id)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"Item is already {row.status}")

    payload = json.loads(row.payload)
    email = payload.get("email", {})
    subject = email.get("subject", "")
    body = email.get("body", "")
    to_email = row.client_email or payload.get("client_email")

    if not to_email:
        raise HTTPException(status_code=400, detail="Client has no email address on file")

    sent = send_email(to_email, subject, body)
    new_status = "approved" if sent else "failed"

    await db.execute(text("""
        UPDATE approval_queue SET status = :status, reviewed_at = now() WHERE id = :id
    """), {"status": new_status, "id": item_id})

    db.add(EmailLog(client_id=row.client_id, subject=subject, body=body, status=new_status))
    await db.commit()

    return {"status": new_status, "sent_to": to_email}


@router.post("/{item_id}/reject")
async def reject_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    _require_uuid(item_id)
    row = await _fetch_own_item(db, item_id, current.id)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"Item is already {row.status}")

    await db.execute(text("""
        UPDATE approval_queue SET status = 'rejected', reviewed_at = now() WHERE id = :id
    """), {"id": item_id})
    await db.commit()

    return {"status": "rejected"}
