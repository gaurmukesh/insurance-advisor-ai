from app.core.llm import chat_mini as chat
from app.core.guardrails import validate_output

SYSTEM_PROMPT = """You are an insurance advisor's assistant writing professional emails in India.
Write warm, clear, and action-oriented emails in simple English.
Always include the advisor's name and a clear call to action.
Always write dates in long format (e.g. "August 1, 2026"), never in ISO or numeric format.
Keep emails concise — under 200 words.
Never use IRDAI-prohibited phrases such as 'guaranteed returns', 'no risk',
'risk-free', '100% safe investment', 'assured profit', or 'tax-free guaranteed'."""


def _parse_email_response(response: str) -> dict:
    lines = response.strip().split("\n")
    subject = ""
    body_lines = []
    in_body = False

    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        elif line.strip() == "BODY:":
            in_body = True
        elif in_body:
            body_lines.append(line)

    return {"subject": subject, "body": "\n".join(body_lines).strip()}


async def generate_premium_reminder_email(
    client_name: str,
    policy_no: str,
    product_name: str,
    insurer_name: str,
    premium_amount: float,
    due_date: str,
    advisor_name: str,
) -> dict:
    user_message = f"""
Write a premium due reminder email with these details:

- Client Name: {client_name}
- Policy Number: {policy_no}
- Product: {product_name} by {insurer_name}
- Premium Amount: ₹{premium_amount:,.0f}
- Due Date: {due_date}
- Advisor Name: {advisor_name}

Return in this exact format:
SUBJECT: <subject line>
BODY:
<email body>
"""
    response = await chat(SYSTEM_PROMPT, user_message, trace_name="email_generator_reminder")
    validate_output(response, context="email_generator_reminder")
    return _parse_email_response(response)


async def generate_followup_email(
    client_name: str,
    advisor_name: str,
    context: str,
) -> dict:
    user_message = f"""
Write a follow-up email for an insurance advisor:

- Client Name: {client_name}
- Advisor Name: {advisor_name}
- Context: {context}

Return in this exact format:
SUBJECT: <subject line>
BODY:
<email body>
"""
    response = await chat(SYSTEM_PROMPT, user_message, trace_name="email_generator_followup")
    validate_output(response, context="email_generator_followup")
    return _parse_email_response(response)
