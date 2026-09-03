"""
Tests for the product knowledge-graph layer: the doc-type gate that protects
against extracting PII from an issued policy PDF, policy<->product linking,
and the overlap/gap query logic that feeds agents' 'Structured Facts' prompt
section. No LLM calls -- these are all pure-SQL/ORM-logic tests against a
real test database, per this repo's existing fast-tier test style.
"""

import pytest
import pytest_asyncio

from app.core.knowledge_graph import find_coverage_gaps, find_coverage_overlaps, link_policy_to_product
from app.core.rag import _looks_like_product_template
from app.models.advisor import Advisor
from app.models.client import Client
from app.models.policy import Policy
from app.models.product import CoverageItem, Product


# ── Doc-type gate ────────────────────────────────────────────────────────────

def test_looks_like_product_template_true_for_generic_spec_sheet():
    text = "Niva Bupa Reassure 2.0\nCoverage Summary\nBenefit Coverage Sub-limit\nKey Exclusions"
    assert _looks_like_product_template(text) is True


def test_looks_like_product_template_false_for_issued_policy():
    text = """HEALTH INSURANCE POLICY DOCUMENT Policy No: SL-HLTH-2024-00421
1. POLICYHOLDER DETAILS
Full Name Amit Singh Date of Birth 15 March 1985 (Age: 39)
Policy Holder ID PH-2024-78421
2. INSURED MEMBERS
# Name Relationship DOB Age Sum Insured"""
    assert _looks_like_product_template(text) is False


# ── Linking ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def advisor_row(db_session):
    row = Advisor(name="KG Test Advisor", email="kg-advisor@example.com", phone="9000000001",
                   password_hash="unused")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest_asyncio.fixture
async def client_row(db_session, advisor_row):
    row = Client(advisor_id=advisor_row.id, name="KG Test Client")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _make_product(db_session, insurer_name="HDFC Life", product_name="Click2Protect",
                         product_type="term", categories: list[str] | None = None) -> Product:
    product = Product(insurer_name=insurer_name, product_name=product_name,
                       product_type=product_type, source_pdf="test.pdf", extraction_status="extracted")
    for category in categories or []:
        product.coverages.append(CoverageItem(benefit_name=category, benefit_category=category))
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


async def _make_policy(db_session, client_row, insurer_name, product_name, policy_no) -> Policy:
    policy = Policy(client_id=client_row.id, insurer_name=insurer_name, product_name=product_name,
                     policy_no=policy_no, policy_type="term", premium_amount=1000.0)
    db_session.add(policy)
    await db_session.commit()
    await db_session.refresh(policy)
    return policy


@pytest.mark.asyncio
async def test_link_policy_to_product_exact_match(db_session, client_row):
    product = await _make_product(db_session, "HDFC Life", "Click2Protect")
    policy = await _make_policy(db_session, client_row, "HDFC Life", "Click2Protect", "POL-001")

    link = await link_policy_to_product(db_session, policy)
    await db_session.commit()

    assert link.match_method == "exact"
    assert link.product_id == product.id


@pytest.mark.asyncio
async def test_link_policy_to_product_unmatched_when_no_product_exists(db_session, client_row):
    policy = await _make_policy(db_session, client_row, "Unknown Insurer", "Unknown Product", "POL-002")

    link = await link_policy_to_product(db_session, policy)
    await db_session.commit()

    assert link.match_method == "unmatched"
    assert link.product_id is None


# ── Query layer ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_coverage_overlaps_detects_shared_category(db_session, client_row):
    product_a = await _make_product(db_session, "HDFC Life", "Click2Protect", categories=["accidental_death"])
    product_b = await _make_product(db_session, "Bajaj Allianz", "Secura", categories=["accidental_death"])

    policy_a = await _make_policy(db_session, client_row, "HDFC Life", "Click2Protect", "POL-A")
    policy_b = await _make_policy(db_session, client_row, "Bajaj Allianz", "Secura", "POL-B")

    await link_policy_to_product(db_session, policy_a)
    await link_policy_to_product(db_session, policy_b)
    await db_session.commit()

    overlaps = await find_coverage_overlaps(db_session, client_row.id)

    assert len(overlaps) == 1
    assert overlaps[0]["benefit_category"] == "accidental_death"
    assert set(overlaps[0]["products"]) == {"HDFC Life Click2Protect", "Bajaj Allianz Secura"}
    assert product_a.id != product_b.id  # sanity: these really are two different products


@pytest.mark.asyncio
async def test_find_coverage_overlaps_empty_when_categories_differ(db_session, client_row):
    await _make_product(db_session, "HDFC Life", "Click2Protect", categories=["accidental_death"])
    await _make_product(db_session, "Niva Bupa", "Reassure", categories=["hospitalisation"])

    policy_a = await _make_policy(db_session, client_row, "HDFC Life", "Click2Protect", "POL-C")
    policy_b = await _make_policy(db_session, client_row, "Niva Bupa", "Reassure", "POL-D")

    await link_policy_to_product(db_session, policy_a)
    await link_policy_to_product(db_session, policy_b)
    await db_session.commit()

    assert await find_coverage_overlaps(db_session, client_row.id) == []


@pytest.mark.asyncio
async def test_find_coverage_gaps_flags_missing_category_for_health_conditions(db_session, client_row):
    await _make_product(db_session, "HDFC Life", "Click2Protect", categories=["accidental_death"])
    policy = await _make_policy(db_session, client_row, "HDFC Life", "Click2Protect", "POL-E")
    await link_policy_to_product(db_session, policy)
    await db_session.commit()

    profile = {"health_conditions": "diabetes", "dependents_detail": "None"}
    gaps = await find_coverage_gaps(db_session, client_row.id, profile)

    assert "critical_illness" in gaps
    assert "hospitalisation" in gaps
    assert "accidental_death" not in gaps  # already owned


@pytest.mark.asyncio
async def test_find_coverage_gaps_empty_when_profile_has_no_signals(db_session, client_row):
    profile = {"health_conditions": "None", "dependents_detail": "None"}
    assert await find_coverage_gaps(db_session, client_row.id, profile) == []
