from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import PolicyProductLink
from app.models.policy import Policy

# Coverage categories a client should probably have, inferred from profile
# signals already collected on Client (health_conditions, dependents_detail).
# Deliberately small and conservative for the first slice -- expand as more
# profile signals get modeled.
EXPECTED_CATEGORIES_BY_PROFILE = {
    "has_health_conditions": {"critical_illness", "hospitalisation"},
    "has_dependents": {"accidental_death"},
}


async def link_policy_to_product(db: AsyncSession, policy: Policy) -> PolicyProductLink:
    """Exact-match on (insurer_name, product_name). Fuzzy matching is a later
    enhancement -- for now, an advisor-entered name that doesn't
    character-match the PDF-extracted product name falls back to
    match_method='unmatched', which is just today's vector-only behavior for
    that policy (not a regression)."""
    product = (await db.execute(
        text("""
            SELECT id FROM products
            WHERE insurer_name = :insurer_name AND product_name = :product_name
        """),
        {"insurer_name": policy.insurer_name, "product_name": policy.product_name},
    )).scalar_one_or_none()

    link = PolicyProductLink(
        policy_id=policy.id,
        product_id=product,
        match_method="exact" if product else "unmatched",
    )
    db.add(link)
    return link


_OWNED_CATEGORIES_SQL = """
    SELECT DISTINCT ci.benefit_category
    FROM coverage_items ci
    JOIN policy_product_link l ON l.product_id = ci.product_id
    JOIN policies pol ON pol.id = l.policy_id
    WHERE pol.client_id = :client_id
"""


async def find_coverage_overlaps(db: AsyncSession, client_id: str) -> list[dict]:
    """Coverage categories present in 2+ of a client's owned, matched products."""
    rows = (await db.execute(text("""
        SELECT ci.benefit_category, p.product_name, p.insurer_name
        FROM coverage_items ci
        JOIN products p            ON p.id = ci.product_id
        JOIN policy_product_link l ON l.product_id = p.id
        JOIN policies pol          ON pol.id = l.policy_id
        WHERE pol.client_id = :client_id
    """), {"client_id": client_id})).all()

    by_category: dict[str, list[str]] = {}
    for r in rows:
        by_category.setdefault(r.benefit_category, []).append(f"{r.insurer_name} {r.product_name}")

    return [
        {"benefit_category": category, "products": sorted(set(products))}
        for category, products in by_category.items()
        if len(set(products)) > 1
    ]


def format_kg_facts_for_prompt(kg_facts: dict | None) -> str:
    """Renders kg_facts (as produced by fetch_kg_facts) into the 'Structured
    Facts' prompt section shared by need_analyzer.py, product_recommender.py,
    and product_matching_agent.py's rank_match."""
    if not kg_facts:
        return "None available."

    lines = []
    for overlap in kg_facts.get("overlaps", []):
        lines.append(f"- OVERLAP: {overlap['benefit_category']} is already covered by more than one "
                      f"owned policy: {', '.join(overlap['products'])} -- avoid recommending another "
                      f"product for this category.")
    for gap in kg_facts.get("structural_gaps", []):
        lines.append(f"- GAP: no owned policy covers '{gap}' -- prioritize this in recommendations.")

    return "\n".join(lines) if lines else "None found."


async def fetch_kg_facts(db: AsyncSession, client_id: str, client_profile: dict) -> dict:
    """Bundles overlap + gap detection into the shape need_analyzer.py and
    product_recommender.py expect for their 'Structured Facts' prompt section."""
    return {
        "overlaps": await find_coverage_overlaps(db, client_id),
        "structural_gaps": await find_coverage_gaps(db, client_id, client_profile),
    }


async def find_coverage_gaps(db: AsyncSession, client_id: str, client_profile: dict) -> list[str]:
    """Coverage categories the client's profile suggests they need, that are
    absent across all of their owned, matched products."""
    owned = {row[0] for row in (await db.execute(
        text(_OWNED_CATEGORIES_SQL), {"client_id": client_id}
    )).all()}

    expected: set[str] = set()
    if (client_profile.get("health_conditions") or "None") != "None":
        expected |= EXPECTED_CATEGORIES_BY_PROFILE["has_health_conditions"]
    if (client_profile.get("dependents_detail") or "None") != "None":
        expected |= EXPECTED_CATEGORIES_BY_PROFILE["has_dependents"]

    return sorted(expected - owned)
