import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "premium_reminder"
LANGUAGE_CODE = "en"


def build_message_body(client_name: str, policy_no: str, amount: float, due_date: str) -> str:
    return (
        f"Hi {client_name}, your policy {policy_no} premium of "
        f"₹{int(amount):,} is due on {due_date}. "
        f"Please pay to avoid lapse. Contact your advisor for help."
    )


async def send_whatsapp_reminder(
    phone: str,
    client_name: str,
    policy_no: str,
    amount: float,
    due_date: str,
) -> tuple[str, str]:
    """
    Send a WhatsApp template message via Meta Cloud API.
    Returns (status, wa_message_id). status is 'sent' or 'failed'.
    """
    if not settings.META_WHATSAPP_TOKEN or not settings.META_PHONE_NUMBER_ID:
        logger.warning("WhatsApp credentials not configured — skipping send")
        return "failed", ""

    url = f"https://graph.facebook.com/v18.0/{settings.META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": f"91{phone.lstrip('0')}",
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": LANGUAGE_CODE},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": client_name},
                        {"type": "text", "text": policy_no},
                        {"type": "text", "text": str(int(amount))},
                        {"type": "text", "text": due_date},
                    ],
                }
            ],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()

        if resp.status_code == 200 and "messages" in data:
            wa_id = data["messages"][0].get("id", "")
            logger.info(f"WhatsApp sent to {phone}, wa_id={wa_id}")
            return "sent", wa_id
        else:
            logger.error(f"WhatsApp API error: {data}")
            return "failed", ""
    except Exception as e:
        logger.error(f"WhatsApp send exception: {e}")
        return "failed", ""
