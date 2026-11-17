"""
Taxonomy of claim decision reasons, and the classifier that maps an insurer's
free-text remark ("Repudiated - PED not disclosed at proposal stage") onto it.

Grouping by raw remark text is useless for "what is the primary reason" --
the same reason is worded a dozen ways across insurers and years -- so every
claim gets a reason_category from this fixed list. Keyword rules handle the
common phrasings deterministically; only remarks no rule matches go to the
LLM, in batches, and its answer is still forced back onto this list.
"""

import json
import re

from app.core.llm import chat_mini

REJECTION_REASONS: dict[str, str] = {
    "non_disclosure": "Pre-existing disease or material fact not disclosed at proposal",
    "waiting_period": "Claim fell within an initial, specific-disease or PED waiting period",
    "policy_exclusion": "Treatment or cause is excluded under the policy wording",
    "policy_lapsed": "Policy was lapsed or not in force on the date of loss",
    "insufficient_documents": "Required documents were missing or not submitted in time",
    "late_intimation": "Claim was intimated or submitted after the allowed window",
    "not_medically_necessary": "Hospitalisation or treatment judged not medically necessary",
    "sum_insured_exhausted": "Sum insured or sub-limit already exhausted",
    "fraud_suspected": "Misrepresentation, forged documents or suspected fraud",
    "other": "Any other reason",
}

APPROVAL_REASONS: dict[str, str] = {
    "covered_event": "Event and treatment clearly covered under the policy wording",
    "complete_documentation": "All required documents submitted and verified",
    "network_cashless": "Treated at a network hospital with cashless pre-authorisation",
    "waiting_period_served": "Waiting periods already completed",
    "disclosure_verified": "Disclosures at proposal verified as accurate",
    "other": "Any other reason",
}

# Ordered: first match wins, so the more specific patterns come first
# (e.g. "PED waiting period" must hit waiting_period, not non_disclosure).
_REJECTION_RULES: list[tuple[str, re.Pattern]] = [
    ("fraud_suspected", re.compile(r"fraud|forg|fabricat|misrepresent|tamper", re.I)),
    ("waiting_period", re.compile(r"waiting\s*period|cooling\s*period|within \d+ (days|months|years) of (inception|cover)", re.I)),
    ("non_disclosure", re.compile(r"non[-\s]?disclos|not disclosed|suppress|concealment|\bPED\b|pre[-\s]?existing", re.I)),
    ("policy_lapsed", re.compile(r"laps|not in force|premium (not|un)paid|grace period", re.I)),
    ("late_intimation", re.compile(r"late (intimation|submission)|delay(ed)? in (intimation|submission)|beyond \d+ days", re.I)),
    ("insufficient_documents", re.compile(r"document|discharge summary|bills? not|kyc|incomplete|query not (replied|answered)", re.I)),
    ("sum_insured_exhausted", re.compile(r"sum insured|sub[-\s]?limit|exhaust|capping|room rent limit", re.I)),
    ("not_medically_necessary", re.compile(r"medically necessary|no active (line of )?treatment|opd|investigation only|observation only", re.I)),
    ("policy_exclusion", re.compile(r"exclu|not covered|cosmetic|self[-\s]?inflicted|alcohol|intoxicat|permanent exclusion", re.I)),
]

_APPROVAL_RULES: list[tuple[str, re.Pattern]] = [
    ("network_cashless", re.compile(r"cashless|network hospital|pre[-\s]?auth", re.I)),
    ("waiting_period_served", re.compile(r"waiting period (completed|served|over)", re.I)),
    ("disclosure_verified", re.compile(r"disclos\w* verified|no (ped|non[-\s]?disclosure)|declarations? (verified|accurate)", re.I)),
    ("complete_documentation", re.compile(r"documents? (complete|verified|in order)|all documents", re.I)),
    ("covered_event", re.compile(r"admissible|covered|payable|as per (policy|terms)|within (scope|terms)", re.I)),
]


def taxonomy_for(status: str) -> dict[str, str]:
    return REJECTION_REASONS if status == "rejected" else APPROVAL_REASONS


def classify_by_rules(status: str, remark: str | None) -> str | None:
    """Keyword-rule classification. None means no rule matched and the remark
    should go to classify_with_llm (pending claims have no reason yet)."""
    if status == "pending" or not remark:
        return None
    rules = _REJECTION_RULES if status == "rejected" else _APPROVAL_RULES
    for category, pattern in rules:
        if pattern.search(remark):
            return category
    return None


async def classify_with_llm(status: str, remarks: list[str]) -> list[str]:
    """Batch-classify remarks no rule matched. Any answer outside the taxonomy
    (or a malformed response) falls back to 'other' rather than inventing a
    new category that would fragment the counts."""
    if not remarks:
        return []
    taxonomy = taxonomy_for(status)
    system = (
        "You classify insurance claim decision remarks into a fixed taxonomy. "
        "Return only a JSON array of category keys, one per remark, in order."
    )
    prompt = (
        "Categories:\n"
        + "\n".join(f"- {key}: {desc}" for key, desc in taxonomy.items())
        + "\n\nRemarks:\n"
        + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(remarks))
    )
    raw = await chat_mini(system, prompt, trace_name="classify_claim_reasons")
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        answers = json.loads(clean)
    except Exception:
        answers = []
    if not isinstance(answers, list) or len(answers) != len(remarks):
        return ["other"] * len(remarks)
    return [a if a in taxonomy else "other" for a in answers]
