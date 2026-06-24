import re

_AADHAAR = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
_PAN     = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
_PHONE   = re.compile(r'\b[6-9]\d{9}\b')
_EMAIL   = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b')


def scrub(text: str) -> str:
    """Strip Indian PII before sending to any external LLM API."""
    text = _AADHAAR.sub("[AADHAAR-REDACTED]", text)
    text = _PAN.sub("[PAN-REDACTED]", text)
    text = _PHONE.sub("[PHONE-REDACTED]", text)
    text = _EMAIL.sub("[EMAIL-REDACTED]", text)
    return text
