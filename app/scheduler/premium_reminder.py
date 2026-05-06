from datetime import date, timedelta
from sqlalchemy import select
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.db.postgres import AsyncSessionLocal
from app.models.policy import Policy
from app.models.client import Client
from app.models.email_log import EmailLog
from app.modules.email_generator import generate_premium_reminder_email
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
            if not client.email:
                logger.warning(f"Skipping {client.name} — no email address")
                continue

            try:
                email_content = generate_premium_reminder_email(
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
                status = "sent"
                logger.info(f"Reminder sent to {client.email} for policy {policy.policy_no}")

            except Exception as e:
                status = "failed"
                logger.error(f"Failed to send reminder to {client.email}: {e}")

            log = EmailLog(
                client_id=client.id,
                policy_id=policy.id,
                subject=email_content.get("subject", "Premium Reminder"),
                body=email_content.get("body", ""),
                status=status,
            )
            db.add(log)

        await db.commit()
