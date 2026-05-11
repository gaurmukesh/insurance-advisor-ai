from datetime import date, timedelta
from sqlalchemy import select
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.db.postgres import AsyncSessionLocal
from app.models.policy import Policy
from app.models.client import Client
from app.models.email_log import EmailLog
from app.models.whatsapp_log import WhatsAppLog
from app.modules.email_generator import generate_premium_reminder_email
from app.modules.whatsapp_handler import send_whatsapp_reminder, build_message_body
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def run_premium_reminder_job(days_ahead: int = 7):
    logger.info(f"Running premium reminder job — checking policies due in {days_ahead} days")

    today = date.today()
    target_date = today + timedelta(days=days_ahead)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Policy, Client)
            .join(Client, Policy.client_id == Client.id)
            .where(Policy.next_due_date == target_date)
        )
        rows = result.all()

        logger.info(f"Found {len(rows)} policies due on {target_date}")

        for policy, client in rows:
            email_content = None

            # ── Email reminder ─────────────────────────────────────────────────
            if client.email:
                try:
                    email_content = await generate_premium_reminder_email(
                        client_name=client.name,
                        policy_no=policy.policy_no,
                        product_name=policy.product_name,
                        insurer_name=policy.insurer_name,
                        premium_amount=policy.premium_amount,
                        due_date=str(policy.next_due_date),
                        advisor_name="Your Advisor",
                    )
                    message = Mail(
                        from_email=settings.SENDGRID_FROM_EMAIL,
                        to_emails=client.email,
                        subject=email_content["subject"],
                        plain_text_content=email_content["body"],
                    )
                    sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
                    sg.send(message)
                    email_status = "sent"
                    logger.info(f"Email sent to {client.email} for policy {policy.policy_no}")
                except Exception as e:
                    email_status = "failed"
                    logger.error(f"Email failed for {client.email}: {e}")

                log = EmailLog(
                    client_id=client.id,
                    policy_id=policy.id,
                    subject=email_content.get("subject", "Premium Reminder") if email_content else "Premium Reminder",
                    body=email_content.get("body", "") if email_content else "",
                    status=email_status,
                )
                db.add(log)
            else:
                logger.warning(f"Skipping email for {client.name} — no email address")

            # ── WhatsApp reminder ──────────────────────────────────────────────
            if client.phone:
                try:
                    wa_status, wa_id = await send_whatsapp_reminder(
                        phone=client.phone,
                        client_name=client.name,
                        policy_no=policy.policy_no,
                        amount=policy.premium_amount,
                        due_date=str(policy.next_due_date),
                    )
                except Exception as e:
                    wa_status, wa_id = "failed", ""
                    logger.error(f"WhatsApp failed for {client.phone}: {e}")

                wa_log = WhatsAppLog(
                    client_id=client.id,
                    policy_id=policy.id,
                    phone=client.phone,
                    template_name="premium_reminder",
                    message_body=build_message_body(
                        client_name=client.name,
                        policy_no=policy.policy_no,
                        amount=policy.premium_amount,
                        due_date=str(policy.next_due_date),
                    ),
                    wa_message_id=wa_id or None,
                    status=wa_status,
                )
                db.add(wa_log)
            else:
                logger.warning(f"Skipping WhatsApp for {client.name} — no phone number")

        await db.commit()
