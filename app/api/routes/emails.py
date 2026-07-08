from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.api.deps import get_current_advisor
from app.db.postgres import get_db
from app.models.advisor import Advisor
from app.models.client import Client
from app.models.policy import Policy
from app.models.email_log import EmailLog
from app.modules.email_generator import generate_premium_reminder_email, generate_followup_email
from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["emails"])


@router.get("/email-logs")
async def get_email_logs(
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    result = await db.execute(
        select(EmailLog)
        .join(Client, EmailLog.client_id == Client.id)
        .where(Client.advisor_id == current.id)
        .order_by(EmailLog.sent_at.desc())
        .limit(100)
    )
    return result.scalars().all()


class ReminderEmailRequest(BaseModel):
    policy_id: str
    advisor_name: str


class FollowupEmailRequest(BaseModel):
    client_id: str
    advisor_name: str
    context: str


def send_email(to_email: str, subject: str, body: str) -> bool:
    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
        return True
    except Exception:
        return False


async def _get_own_policy_client(db: AsyncSession, policy_id: str, advisor: Advisor):
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == policy_id)
    )
    row = result.one_or_none()
    if not row or row[1].advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Policy not found")
    return row


async def _get_own_client(db: AsyncSession, client_id: str, advisor: Advisor) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client or client.advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/draft-email/reminder")
async def draft_reminder(
    data: ReminderEmailRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    policy, client = await _get_own_policy_client(db, data.policy_id, current)

    email_content = await generate_premium_reminder_email(
        client_name=client.name,
        policy_no=policy.policy_no,
        product_name=policy.product_name,
        insurer_name=policy.insurer_name,
        premium_amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
        advisor_name=data.advisor_name,
    )
    return {"client_name": client.name, "client_email": client.email, **email_content}


@router.post("/send-email/reminder")
async def send_reminder(
    data: ReminderEmailRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    policy, client = await _get_own_policy_client(db, data.policy_id, current)
    if not client.email:
        raise HTTPException(status_code=400, detail="Client has no email address")

    email_content = await generate_premium_reminder_email(
        client_name=client.name,
        policy_no=policy.policy_no,
        product_name=policy.product_name,
        insurer_name=policy.insurer_name,
        premium_amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
        advisor_name=data.advisor_name,
    )

    sent = send_email(client.email, email_content["subject"], email_content["body"])
    status = "sent" if sent else "failed"

    log = EmailLog(
        client_id=client.id,
        policy_id=policy.id,
        subject=email_content["subject"],
        body=email_content["body"],
        status=status,
    )
    db.add(log)
    await db.commit()

    return {"status": status, "client_email": client.email, **email_content}


@router.get("/email-drafts")
async def get_email_drafts(
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    result = await db.execute(
        select(EmailLog, Client)
        .join(Client, EmailLog.client_id == Client.id)
        .where(EmailLog.status == "pending")
        .where(Client.advisor_id == current.id)
        .order_by(EmailLog.sent_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": log.id,
            "client_id": log.client_id,
            "client_name": client.name,
            "client_email": client.email,
            "policy_id": log.policy_id,
            "subject": log.subject,
            "body": log.body,
            "edited_body": log.edited_body,
            "status": log.status,
            "sent_at": log.sent_at,
        }
        for log, client in rows
    ]


class ApproveRequest(BaseModel):
    edited_body: Optional[str] = None


async def _get_own_draft(db: AsyncSession, draft_id: str, advisor: Advisor):
    result = await db.execute(
        select(EmailLog, Client)
        .join(Client, EmailLog.client_id == Client.id)
        .where(EmailLog.id == draft_id)
    )
    row = result.one_or_none()
    if not row or row[1].advisor_id != advisor.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    return row


@router.post("/email-drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    data: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    log, client = await _get_own_draft(db, draft_id, current)
    if log.status != "pending":
        raise HTTPException(status_code=400, detail="Draft is not in pending state")
    if not client.email:
        raise HTTPException(status_code=400, detail="Client has no email address")

    body_to_send = data.edited_body or log.body
    sent = send_email(client.email, log.subject, body_to_send)

    log.edited_body = data.edited_body or None
    log.status = "sent" if sent else "failed"
    await db.commit()

    return {"status": log.status, "client_email": client.email}


@router.post("/email-drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    log, _client = await _get_own_draft(db, draft_id, current)
    if log.status != "pending":
        raise HTTPException(status_code=400, detail="Draft is not in pending state")

    log.status = "rejected"
    await db.commit()
    return {"status": "rejected"}


@router.post("/draft-email/followup")
async def draft_followup(
    data: FollowupEmailRequest,
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    client = await _get_own_client(db, data.client_id, current)

    email_content = await generate_followup_email(
        client_name=client.name,
        advisor_name=data.advisor_name,
        context=data.context,
    )
    return {"client_name": client.name, "client_email": client.email, **email_content}
