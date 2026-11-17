"""
Tests for claims settlement analysis: reason classification, CSV import,
primary rejection/approval reasons, and rejection-vs-background correlation.

The classifier and correlation tests are pure functions; the import and
reason-breakdown tests run against the real test database like the rest of
this suite. The LLM is patched everywhere it could be reached.
"""

import random
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.claim_reasons import classify_by_rules, classify_with_llm
from app.core.claims_analytics import Period, compute_rejection_correlation, reason_breakdown
from app.core.claims_ingest import import_claims_csv
from scripts.generate_synthetic_claims import APPROVAL_REMARKS, REJECTION_REMARKS

HEADER = ("claim_no,claimant_ref,age,gender,pre_existing_conditions,policy_tenure_years,"
          "claim_amount,settled_amount,filed_date,decision_date,status,decision_reason_text,reason_category")


def _csv(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# ── Classification ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("status,remarks", [("rejected", REJECTION_REMARKS), ("approved", APPROVAL_REMARKS)])
def test_every_synthetic_remark_classifies_to_its_intended_category(status, remarks):
    for category, texts in remarks.items():
        for text in texts:
            assert classify_by_rules(status, text) == category, text


def test_ped_waiting_period_is_waiting_period_not_non_disclosure():
    assert classify_by_rules("rejected", "PED waiting period of 4 years not completed") == "waiting_period"


def test_pending_and_unmatched_remarks_are_left_for_later():
    assert classify_by_rules("pending", "Admissible as per policy terms") is None
    assert classify_by_rules("rejected", "Decision as per underwriter") is None


async def test_llm_answers_outside_taxonomy_fall_back_to_other():
    with patch("app.core.claim_reasons.chat_mini", new_callable=AsyncMock,
               return_value='["waiting_period", "made_up_reason"]'):
        assert await classify_with_llm("rejected", ["a", "b"]) == ["waiting_period", "other"]


async def test_malformed_llm_response_falls_back_to_other():
    with patch("app.core.claim_reasons.chat_mini", new_callable=AsyncMock, return_value="not json"):
        assert await classify_with_llm("rejected", ["a", "b"]) == ["other", "other"]


# ── Correlation (pure) ───────────────────────────────────────────────────────

def _records(n=2000, seed=7):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        ped = rng.random() < 0.3
        rejected = rng.random() < (0.45 if ped else 0.08)
        out.append({
            "age": rng.randint(20, 70), "annual_income": rng.uniform(2e5, 3e6),
            "policy_tenure_years": rng.uniform(0, 8), "prior_claims_count": rng.randint(0, 4),
            "pre_existing_conditions": ped, "gender": rng.choice(["male", "female"]),
            "occupation": "salaried", "city_tier": rng.choice(["tier1", "tier2"]),
            "state": "Karnataka", "purchase_channel": "agent",
            "rejected": rejected, "reason_category": "non_disclosure" if rejected and ped else "other",
        })
    return out


def test_correlation_ranks_the_planted_factor_first_and_gender_negligible():
    result = compute_rejection_correlation(_records())

    top = result["attributes"][0]
    assert top["attribute"] == "pre_existing_conditions"
    assert top["significant"] and top["strength"] in ("moderate", "strong")
    assert top["buckets"][0]["value"] == "yes"
    assert top["buckets"][0]["top_rejection_reason"] == "non_disclosure"
    assert result["strongest_factors"][0] == "pre_existing_conditions"

    gender = next(a for a in result["attributes"] if a["attribute"] == "gender")
    assert gender["strength"] == "negligible"


def test_single_valued_attribute_reports_insufficient_data_instead_of_crashing():
    occupation = next(a for a in compute_rejection_correlation(_records())["attributes"]
                      if a["attribute"] == "occupation")
    assert occupation["cramers_v"] is None
    assert occupation["strength"] == "insufficient_data"


def test_correlation_on_empty_input():
    result = compute_rejection_correlation([])
    assert result["decided_claims"] == 0
    assert result["strongest_factors"] == []


# ── Import + reason breakdown (DB) ───────────────────────────────────────────

async def test_import_classifies_dedupes_and_reports_bad_rows(db_session):
    content = _csv(
        f"C1,P1,40,male,yes,1.5,50000,0,{_days_ago(40)},{_days_ago(30)},rejected,PED not disclosed at proposal,",
        f"C2,P1,40,male,yes,1.5,20000,20000,{_days_ago(40)},{_days_ago(20)},approved,Cashless approved at network hospital,",
        f"C3,P2,30,female,no,4,10000,0,{_days_ago(40)},{_days_ago(20)},rejected,Some unusual remark,",
        f"C4,P2,30,female,no,4,10000,0,{_days_ago(40)},{_days_ago(20)},rejected,whatever,fraud_suspected",
        f"C1,P1,40,male,yes,1.5,50000,0,{_days_ago(40)},{_days_ago(30)},rejected,duplicate in file,",
        f"C5,P3,30,female,no,4,10000,0,{_days_ago(40)},,closed,,",
    )
    result = await import_claims_csv(db_session, content, use_llm=False)

    assert result.inserted == 4
    assert result.skipped_duplicates == 1
    assert result.claimants_created == 2
    assert result.classified_by == {"source": 1, "rule": 3, "llm": 0}
    assert [e["row"] for e in result.errors] == [7]

    again = await import_claims_csv(db_session, content, use_llm=False)
    assert again.inserted == 0 and again.skipped_duplicates == 5


async def test_import_rejects_csv_missing_required_columns(db_session):
    result = await import_claims_csv(db_session, "claim_no,status\nC1,approved\n", use_llm=False)
    assert result.inserted == 0
    assert "Missing required columns" in result.errors[0]["error"]


async def test_primary_rejection_reason_within_past_year(db_session):
    content = _csv(
        f"R1,P1,40,male,yes,1,1000,0,{_days_ago(100)},{_days_ago(90)},rejected,PED not disclosed,",
        f"R2,P2,41,male,yes,1,1000,0,{_days_ago(100)},{_days_ago(80)},rejected,Pre-existing diabetes suppressed,",
        f"R3,P3,42,female,no,0.5,1000,0,{_days_ago(100)},{_days_ago(70)},rejected,Within 30 days initial waiting period,",
        f"R4,P4,43,female,no,5,1000,0,{_days_ago(100)},{_days_ago(60)},rejected,Odd remark,",
        f"R5,P5,44,female,no,5,1000,0,{_days_ago(100)},{_days_ago(60)},rejected,Odd remark 2,",
        f"R6,P6,45,female,no,5,1000,0,{_days_ago(100)},{_days_ago(60)},rejected,Odd remark 3,",
        # Outside the 12-month window: must not count, even though it would win.
        *(f"OLD{i},P7,45,male,no,5,1000,0,{_days_ago(800)},{_days_ago(790)},rejected,Policy lapsed,"
          for i in range(5)),
        f"A1,P8,30,male,no,5,1000,1000,{_days_ago(100)},{_days_ago(50)},approved,Admissible as per policy terms,",
    )
    await import_claims_csv(db_session, content, use_llm=False)

    result = await reason_breakdown(db_session, "rejected", Period.last_months(12))

    assert result["claims_in_outcome"] == 6
    assert result["total_decided_claims"] == 7
    # "other" has 3 claims but is a catch-all, so the top named reason is primary.
    assert result["reasons"][0]["category"] == "other"
    assert result["primary_reason"]["category"] == "non_disclosure"
    assert result["primary_reason"]["count"] == 2


async def test_primary_approval_reason_includes_partial_approvals(db_session):
    content = _csv(
        f"A1,P1,30,male,no,5,1000,1000,{_days_ago(60)},{_days_ago(50)},approved,Cashless approved at network hospital,",
        f"A2,P2,30,male,no,5,1000,700,{_days_ago(60)},{_days_ago(50)},partially_approved,Pre-authorisation granted,",
        f"A3,P3,30,male,no,5,1000,1000,{_days_ago(60)},{_days_ago(50)},approved,All documents verified,",
    )
    await import_claims_csv(db_session, content, use_llm=False)

    result = await reason_breakdown(db_session, "approved", Period.last_months(12))

    assert result["claims_in_outcome"] == 3
    assert result["primary_reason"]["category"] == "network_cashless"
    assert result["primary_reason"]["share_pct"] == 66.7


# ── API ──────────────────────────────────────────────────────────────────────

async def test_analysis_endpoints_require_auth(client):
    response = await client.get("/api/v1/claims/analysis/rejection-reasons")
    assert response.status_code == 401


async def test_advisor_role_cannot_import_claims(client, auth_headers):
    response = await client.post(
        "/api/v1/claims/import", headers=auth_headers,
        files={"file": ("claims.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 403


async def test_rejection_correlation_endpoint(client, auth_headers, db_session):
    rows = [
        f"K{i},P{i},{30 + i % 30},{'male' if i % 2 else 'female'},{'yes' if i % 3 == 0 else 'no'},2,1000,0,"
        f"{_days_ago(60)},{_days_ago(30)},{'rejected' if i % 3 == 0 else 'approved'},"
        f"{'PED not disclosed' if i % 3 == 0 else 'Admissible as per policy terms'},"
        for i in range(90)
    ]
    await import_claims_csv(db_session, _csv(*rows), use_llm=False)

    response = await client.get("/api/v1/claims/analysis/rejection-correlation?months=12", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["decided_claims"] == 90
    assert body["attributes"][0]["attribute"] == "pre_existing_conditions"
    assert "caveat" in body
