# IRDAI-prohibited phrases in insurance marketing
_PROHIBITED = [
    "guaranteed returns",
    "no risk",
    "100% safe investment",
    "tax-free guaranteed",
    "assured profit",
    "risk-free",
]


def validate_output(text: str, context: str = "") -> str:
    """
    Reject LLM outputs containing regulatory violations.
    Raises ValueError — caller decides whether to retry or surface the error.
    """
    lower = text.lower()
    for phrase in _PROHIBITED:
        if phrase in lower:
            raise ValueError(
                f"Output contains IRDAI-prohibited claim: '{phrase}'. "
                f"Context: {context}"
            )
    return text
