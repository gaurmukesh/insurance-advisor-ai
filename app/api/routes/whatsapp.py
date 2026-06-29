from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.postgres import get_db
from app.models.client import Client
from app.models.policy import Policy
from app.models.whatsapp_log import WhatsAppLog
from app.modules.whatsapp_handler import send_whatsapp_reminder, build_message_body
from app.core.config import settings
import logging

router = APIRouter(prefix="/api/v1", tags=["whatsapp"])
logger = logging.getLogger(__name__)


# ── Meta webhook verification ──────────────────────────────────────────────────

@router.get("/whatsapp/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive incoming WhatsApp messages / delivery status updates."""
    from sqlalchemy import text
    body = await request.json()
    logger.info("WhatsApp webhook received")

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for status in value.get("statuses", []):
                    wa_id = status.get("id")
                    new_status = status.get("status")
                    if wa_id and new_status:
                        await db.execute(
                            text("UPDATE whatsapp_logs SET status = :s WHERE wa_message_id = :w"),
                            {"s": new_status, "w": wa_id},
                        )

                for msg in value.get("messages", []):
                    from_phone = msg.get("from", "").lstrip("91")
                    msg_type = msg.get("type", "")
                    msg_text = ""
                    if msg_type == "text":
                        msg_text = msg.get("text", {}).get("body", "")

                    if from_phone:
                        client_row = (await db.execute(
                            select(Client).where(Client.phone == from_phone)
                        )).scalar_one_or_none()
                        if client_row:
                            await db.execute(
                                text("""
                                    INSERT INTO interactions
                                        (client_id, interaction_type, notes, created_at)
                                    VALUES (:cid, 'whatsapp_inbound', :notes, now())
                                """),
                                {
                                    "cid": client_row.id,
                                    "notes": f"WhatsApp ({msg_type}): {msg_text[:500]}",
                                },
                            )

        await db.commit()
    except Exception as exc:
        logger.error(f"WhatsApp webhook processing error: {exc}")

    return {"status": "ok"}


# ── WhatsApp logs ──────────────────────────────────────────────────────────────

@router.get("/whatsapp-logs")
async def get_whatsapp_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WhatsAppLog).order_by(WhatsAppLog.sent_at.desc()).limit(100)
    )
    return result.scalars().all()


# ── Manual send ───────────────────────────────────────────────────────────────

class WhatsAppReminderRequest(BaseModel):
    policy_id: str


@router.post("/send-whatsapp/reminder")
async def send_whatsapp_reminder_manual(
    data: WhatsAppReminderRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == data.policy_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy, client = row
    if not client.phone:
        raise HTTPException(status_code=400, detail="Client has no phone number")

    status, wa_id = await send_whatsapp_reminder(
        phone=client.phone,
        client_name=client.name,
        policy_no=policy.policy_no,
        amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
    )

    message_body = build_message_body(
        client_name=client.name,
        policy_no=policy.policy_no,
        amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
    )

    log = WhatsAppLog(
        client_id=client.id,
        policy_id=policy.id,
        phone=client.phone,
        template_name="premium_reminder",
        message_body=message_body,
        wa_message_id=wa_id or None,
        status=status,
    )
    db.add(log)
    await db.commit()

    return {
        "status": status,
        "phone": client.phone,
        "client_name": client.name,
        "message": message_body,
    }
