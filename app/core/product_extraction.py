import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat
from app.models.product import CoverageItem, ExclusionItem, Product

logger = logging.getLogger(__name__)

# Closed vocabulary: raw benefit/exclusion phrasing never string-matches across
# insurers (e.g. "In-patient Hospitalisation" vs "Hospitalisation (In-patient)"),
# so cross-product overlap/gap queries need a shared tag space instead.
COVERAGE_CATEGORIES = {
    "hospitalisation", "critical_illness", "accidental_death", "accidental_disability",
    "maternity", "opd", "dental", "mental_wellness", "organ_donor",
    "restoration_of_sum_insured", "ayush", "home_care", "other",
}
EXCLUSION_CATEGORIES = {
    "pre_existing_disease", "cosmetic", "self_inflicted", "war_nuclear",
    "dental_non_accident", "obesity", "experimental_treatment", "substance_abuse",
    "waiting_period", "other",
}

EXTRACTION_SYSTEM_PROMPT = f"""You extract structured facts from an Indian insurance
product specification document. Return JSON only, no markdown fences.

Schema:
{{
  "insurer_name": "...",
  "product_name": "...",
  "product_type": "term|health|motor|ulip|personal_accident",
  "coverages": [
    {{"benefit_name": "...", "benefit_category": "<one of: {', '.join(sorted(COVERAGE_CATEGORIES))}>",
      "coverage_amount_text": "...", "sub_limit_note": "..."}}
  ],
  "exclusions": [
    {{"exclusion_text": "...", "exclusion_category": "<one of: {', '.join(sorted(EXCLUSION_CATEGORIES))}>"}}
  ]
}}
If a field cannot be determined, use null. Use ONLY the category values listed above --
do not invent new ones."""


def _parse_llm_json(raw: str) -> dict | None:
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        return None


def _clamp_category(value, allowed: set[str]) -> str:
    if value in allowed:
        return value
    if value:
        logger.warning(f"product_extraction: unmapped category {value!r}, bucketing to 'other'")
    return "other"


async def extract_and_store_product_kg(db: AsyncSession, full_text: str, source: str) -> None:
    """Extracts structured coverage/exclusion facts from a product spec PDF's
    text and upserts a Product + its CoverageItem/ExclusionItem children.

    Never raises: a failed LLM call or unparseable output is recorded as a
    Product row with extraction_status='failed' (or, for a call failure,
    skipped entirely) rather than propagating, so the caller's chunk
    ingestion -- already committed -- is never affected by this step.

    Upserts by (insurer_name, product_name) rather than by source_pdf, so a
    re-ingestion after a prompt change replaces stale coverage/exclusion rows
    instead of colliding with the products.uq_product_identity constraint.
    """
    try:
        raw = await chat(EXTRACTION_SYSTEM_PROMPT, full_text[:8000], trace_name="product_extraction")
    except Exception as e:
        logger.error(f"product_extraction: LLM call failed for {source} — {e}")
        return

    data = _parse_llm_json(raw)
    if not data or not data.get("insurer_name") or not data.get("product_name"):
        logger.error(f"product_extraction: could not parse structured output for {source}")
        db.add(Product(
            insurer_name=f"unknown ({source})",
            product_name=source,
            product_type="other",
            source_pdf=source,
            extraction_status="failed",
            raw_extraction_json=raw,
        ))
        return

    existing = (await db.execute(
        select(Product).where(
            Product.insurer_name == data["insurer_name"],
            Product.product_name == data["product_name"],
        )
    )).scalar_one_or_none()

    if existing:
        existing.coverages.clear()
        existing.exclusions.clear()
        product = existing
    else:
        product = Product(insurer_name=data["insurer_name"], product_name=data["product_name"])
        db.add(product)

    product.product_type = data.get("product_type") or "other"
    product.source_pdf = source
    product.extraction_status = "extracted"
    # naive UTC, matching this codebase's other DateTime columns (none use
    # timezone=True) -- a tz-aware value here fails asyncpg's TIMESTAMP bind.
    product.extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    product.raw_extraction_json = raw

    for item in data.get("coverages") or []:
        product.coverages.append(CoverageItem(
            benefit_name=(item.get("benefit_name") or "")[:150],
            benefit_category=_clamp_category(item.get("benefit_category"), COVERAGE_CATEGORIES),
            coverage_amount_text=item.get("coverage_amount_text") or None,
            sub_limit_note=item.get("sub_limit_note") or None,
        ))

    for item in data.get("exclusions") or []:
        product.exclusions.append(ExclusionItem(
            exclusion_text=(item.get("exclusion_text") or "")[:500],
            exclusion_category=_clamp_category(item.get("exclusion_category"), EXCLUSION_CATEGORIES),
        ))

    await db.flush()
