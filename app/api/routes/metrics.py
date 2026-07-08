from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from datetime import date, timedelta
from app.api.deps import get_current_advisor
from app.db.postgres import get_db
from app.models.advisor import Advisor
from app.models.client import Client
from app.models.policy import Policy
from app.models.email_log import EmailLog
from app.models.whatsapp_log import WhatsAppLog

router = APIRouter(prefix="/api/v1", tags=["metrics"])


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    advisor_id = current.id
    # --- Lead stats ---
    lead_rows = await db.execute(
        select(Client.status, func.count(Client.id).label("count"))
        .where(Client.advisor_id == advisor_id)
        .group_by(Client.status)
    )
    lead_by_status = {row.status: row.count for row in lead_rows}
    total_leads = sum(lead_by_status.values())
    converted = lead_by_status.get("converted", 0)
    conversion_rate = round(converted / total_leads * 100, 1) if total_leads else 0.0

    # --- Policy stats ---
    today = date.today()
    policy_rows = await db.execute(
        select(
            func.count(Policy.id).label("total"),
            func.sum(Policy.premium_amount).label("total_premium"),
            func.sum(
                case((Policy.next_due_date.between(today, today + timedelta(days=7)), 1), else_=0)
            ).label("due_7d"),
            func.sum(
                case((Policy.next_due_date.between(today, today + timedelta(days=30)), 1), else_=0)
            ).label("due_30d"),
        )
        .join(Client, Client.id == Policy.client_id)
        .where(Client.advisor_id == advisor_id)
    )
    p = policy_rows.one()

    # --- Email stats ---
    email_rows = await db.execute(
        select(EmailLog.status, func.count(EmailLog.id).label("count"))
        .join(Client, Client.id == EmailLog.client_id)
        .where(Client.advisor_id == advisor_id)
        .group_by(EmailLog.status)
    )
    email_by_status = {row.status: row.count for row in email_rows}

    # --- WhatsApp stats ---
    wa_rows = await db.execute(
        select(WhatsAppLog.status, func.count(WhatsAppLog.id).label("count"))
        .join(Client, Client.id == WhatsAppLog.client_id)
        .where(Client.advisor_id == advisor_id)
        .group_by(WhatsAppLog.status)
    )
    wa_by_status = {row.status: row.count for row in wa_rows}

    # --- Recent activity (last 10 emails + WA combined, sorted) ---
    recent_emails = await db.execute(
        select(Client.name, EmailLog.subject, EmailLog.status, EmailLog.sent_at)
        .join(Client, Client.id == EmailLog.client_id)
        .where(Client.advisor_id == advisor_id)
        .order_by(EmailLog.sent_at.desc())
        .limit(5)
    )
    recent_wa = await db.execute(
        select(Client.name, WhatsAppLog.template_name, WhatsAppLog.status, WhatsAppLog.sent_at)
        .join(Client, Client.id == WhatsAppLog.client_id)
        .where(Client.advisor_id == advisor_id)
        .order_by(WhatsAppLog.sent_at.desc())
        .limit(5)
    )

    activity = []
    for row in recent_emails:
        activity.append({
            "type": "email",
            "client": row.name,
            "detail": row.subject,
            "status": row.status,
            "time": row.sent_at.isoformat() if row.sent_at else None,
        })
    for row in recent_wa:
        activity.append({
            "type": "whatsapp",
            "client": row.name,
            "detail": row.template_name,
            "status": row.status,
            "time": row.sent_at.isoformat() if row.sent_at else None,
        })
    activity.sort(key=lambda x: x["time"] or "", reverse=True)

    return {
        "leads": {
            "total": total_leads,
            "by_status": {
                "new": lead_by_status.get("new", 0),
                "contacted": lead_by_status.get("contacted", 0),
                "interested": lead_by_status.get("interested", 0),
                "converted": converted,
                "lost": lead_by_status.get("lost", 0),
            },
            "conversion_rate": conversion_rate,
        },
        "policies": {
            "total": p.total or 0,
            "total_premium": round(p.total_premium or 0, 2),
            "due_in_7_days": p.due_7d or 0,
            "due_in_30_days": p.due_30d or 0,
        },
        "emails": {
            "total": sum(email_by_status.values()),
            "by_status": email_by_status,
        },
        "whatsapp": {
            "total": sum(wa_by_status.values()),
            "by_status": wa_by_status,
        },
        "recent_activity": activity[:10],
    }
