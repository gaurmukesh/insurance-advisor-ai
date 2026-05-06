from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.db.postgres import get_db
from app.models.client import Client
from app.models.policy import Policy
from app.models.email_log import EmailLog
from app.modules.email_generator import generate_premium_reminder_email, generate_followup_email
from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["emails"])


@router.get("/email-logs")
async def get_email_logs(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(EmailLog).order_by(EmailLog.sent_at.desc()).limit(100))
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


@router.post("/draft-email/reminder")
async def draft_reminder(data: ReminderEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == data.policy_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy, client = row
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
async def send_reminder(data: ReminderEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == data.policy_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy, client = row
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


@router.post("/draft-email/followup")
async def draft_followup(data: FollowupEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    email_content = await generate_followup_email(
        client_name=client.name,
        advisor_name=data.advisor_name,
        context=data.context,
    )
    return {"client_name": client.name, "client_email": client.email, **email_content}
