"""
Generates a synthetic multi-year claims history as CSV, in the format
app/core/claims_ingest.py imports, so the analysis endpoints have something
realistic to run on before real insurer/TPA extracts are available.

The data has deliberate, known signals baked in, so the analysis output can be
sanity-checked against them:
  - pre-existing conditions  -> much higher non-disclosure rejections
  - policy tenure < 2 years  -> waiting-period rejections
  - 3+ prior claims          -> more fraud/misrepresentation rejections
  - online purchase channel  -> somewhat more non-disclosure (self-filled proposals)
  - gender                   -> no effect at all (should show as negligible)

Usage:
    python scripts/generate_synthetic_claims.py --claims 20000 --years 6 --out data/claims/synthetic_claims.csv
    python scripts/generate_synthetic_claims.py --claims 20000 --years 6 --load   # also import into DATABASE_URL
"""

import argparse
import asyncio
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COLUMNS = [
    "claim_no", "claimant_ref", "age", "gender", "occupation", "annual_income", "city_tier",
    "state", "pre_existing_conditions", "policy_tenure_years", "prior_claims_count",
    "purchase_channel", "insurer_name", "policy_type", "claim_type", "claim_amount",
    "settled_amount", "filed_date", "decision_date", "status", "decision_reason_text",
    "reason_category",
]

INSURERS = ["Star Health", "Niva Bupa", "HDFC ERGO", "ICICI Lombard", "Care Health", "Bajaj Allianz"]
OCCUPATIONS = ["salaried", "self_employed", "business", "retired", "homemaker", "student"]
STATES = ["Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Uttar Pradesh", "Gujarat", "West Bengal", "Telangana"]
CHANNELS = ["agent", "online", "bancassurance", "broker"]

# Wording varies on purpose -- the classifier has to normalise it.
REJECTION_REMARKS = {
    "non_disclosure": [
        "Repudiated - PED (diabetes) not disclosed at proposal stage",
        "Claim denied due to non-disclosure of material facts",
        "Pre-existing hypertension suppressed in proposal form",
    ],
    "waiting_period": [
        "Ailment falls under 2 year specific disease waiting period",
        "Claim within 30 days initial waiting period",
        "PED waiting period of 3 years not completed",
    ],
    "policy_exclusion": [
        "Cosmetic procedure - permanent exclusion under policy",
        "Treatment not covered as per policy exclusions clause 4.2",
        "Injury due to alcohol intoxication - excluded",
    ],
    "policy_lapsed": [
        "Policy lapsed on date of admission, premium unpaid",
        "Policy not in force at time of loss",
    ],
    "insufficient_documents": [
        "Discharge summary and final bills not submitted",
        "Query not replied within stipulated time - documents pending",
        "Incomplete KYC documents",
    ],
    "late_intimation": [
        "Late intimation - claim reported beyond 30 days of discharge",
        "Delay in submission of claim documents",
    ],
    "not_medically_necessary": [
        "Admission for investigation only, no active line of treatment",
        "Hospitalisation not medically necessary - OPD treatable",
    ],
    "sum_insured_exhausted": [
        "Sum insured exhausted by earlier claims in policy year",
        "Room rent sub-limit exceeded, balance not payable",
    ],
    "fraud_suspected": [
        "Forged hospital bills detected on verification",
        "Misrepresentation of date of accident - claim repudiated",
    ],
}

APPROVAL_REMARKS = {
    "network_cashless": [
        "Cashless approved at network hospital",
        "Pre-authorisation granted, settled cashless",
    ],
    "complete_documentation": [
        "All documents verified and in order - claim settled",
        "Documents complete, reimbursement processed",
    ],
    "waiting_period_served": ["Waiting period completed, claim admissible"],
    "disclosure_verified": ["Declarations verified accurate, claim payable"],
    "covered_event": [
        "Admissible as per policy terms",
        "Claim payable within scope of cover",
    ],
}


def _claimant(rng: random.Random, ref: str) -> dict:
    age = int(rng.triangular(18, 80, 40))
    pre_existing = rng.random() < (0.12 + 0.006 * max(0, age - 35))
    return {
        "claimant_ref": ref,
        "age": age,
        "gender": rng.choice(["male", "female"]),
        "occupation": "retired" if age >= 62 else rng.choice(OCCUPATIONS[:3] + OCCUPATIONS[4:]),
        "annual_income": round(rng.lognormvariate(13.4, 0.7), -3),
        "city_tier": rng.choices(["tier1", "tier2", "tier3"], weights=[45, 35, 20])[0],
        "state": rng.choice(STATES),
        "pre_existing_conditions": pre_existing,
        "policy_tenure_years": round(rng.expovariate(1 / 3.5), 1),
        "prior_claims_count": min(6, int(rng.expovariate(1 / 0.8))),
        "purchase_channel": rng.choices(CHANNELS, weights=[45, 30, 15, 10])[0],
    }


def _rejection_reason(rng: random.Random, c: dict) -> str | None:
    """Independent per-reason hazards driven by background -- this is where
    the known signals in the module docstring come from."""
    hazards = {
        "non_disclosure": 0.015 + (0.16 if c["pre_existing_conditions"] else 0)
                          + (0.03 if c["purchase_channel"] == "online" else 0),
        "waiting_period": 0.01 + (0.14 if c["policy_tenure_years"] < 2 else 0)
                          + (0.05 if c["pre_existing_conditions"] and c["policy_tenure_years"] < 3 else 0),
        "policy_exclusion": 0.03,
        "policy_lapsed": 0.012,
        "insufficient_documents": 0.025 + (0.01 if c["city_tier"] == "tier3" else 0),
        "late_intimation": 0.012,
        "not_medically_necessary": 0.015,
        "sum_insured_exhausted": 0.008 + 0.006 * c["prior_claims_count"],
        "fraud_suspected": 0.004 + (0.05 if c["prior_claims_count"] >= 3 else 0),
    }
    hits = [reason for reason, p in hazards.items() if rng.random() < p]
    return rng.choice(hits) if hits else None


def generate(n_claims: int, years: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    today = date.today()
    start = today - timedelta(days=365 * years)
    claimants = [_claimant(rng, f"CLT-{i:06d}") for i in range(max(1, n_claims // 2))]

    rows = []
    for i in range(n_claims):
        c = rng.choice(claimants)
        policy_type = rng.choices(["health", "personal_accident", "term", "motor"], weights=[70, 10, 8, 12])[0]
        claim_type = (
            "death" if policy_type == "term"
            else rng.choice(["cashless", "reimbursement"]) if policy_type == "health"
            else "accident"
        )
        filed = start + timedelta(days=rng.randrange((today - start).days))
        decision = filed + timedelta(days=rng.randint(3, 60))
        amount = round(rng.lognormvariate(11.3, 0.9), -2)
        if policy_type == "term":
            amount = rng.choice([2_500_000, 5_000_000, 10_000_000])

        if decision > today:
            status, decision, remark, category, settled = "pending", None, "", "", ""
        elif (reason := _rejection_reason(rng, c)) is not None:
            status, category, settled = "rejected", reason, 0
            remark = rng.choice(REJECTION_REMARKS[reason])
        else:
            partial = rng.random() < 0.18
            status = "partially_approved" if partial else "approved"
            settled = round(amount * (rng.uniform(0.55, 0.9) if partial else 1.0), -2)
            if claim_type == "cashless":
                category = "network_cashless"
            elif c["pre_existing_conditions"]:
                category = rng.choice(["disclosure_verified", "waiting_period_served", "covered_event"])
            else:
                category = rng.choices(
                    ["complete_documentation", "covered_event", "waiting_period_served"], weights=[45, 45, 10]
                )[0]
            remark = rng.choice(APPROVAL_REMARKS[category])

        rows.append({
            **c,
            "claim_no": f"CLM-{filed.year}-{i:07d}",
            "insurer_name": rng.choice(INSURERS),
            "policy_type": policy_type,
            "claim_type": claim_type,
            "claim_amount": amount,
            "settled_amount": settled,
            "filed_date": filed.isoformat(),
            "decision_date": decision.isoformat() if decision else "",
            "status": status,
            "decision_reason_text": remark,
            # Left blank so import exercises the classifier, same as real extracts.
            "reason_category": "",
        })
        c["prior_claims_count"] = min(6, c["prior_claims_count"] + (1 if rng.random() < 0.3 else 0))
    return rows


def write_csv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


async def load(out: Path) -> None:
    from app.core.claims_ingest import import_claims_csv
    from app.db.postgres import AsyncSessionLocal, init_db
    import app.models.advisor  # noqa: F401  (resolve relationships before create_all)
    import app.models.client  # noqa: F401
    import app.models.policy  # noqa: F401
    import app.models.email_log  # noqa: F401
    import app.models.whatsapp_log  # noqa: F401
    import app.models.interaction  # noqa: F401
    import app.models.claim  # noqa: F401

    await init_db()
    async with AsyncSessionLocal() as db:
        result = await import_claims_csv(db, out.read_text(), use_llm=False)
    print(f"Imported {result.inserted} claims ({result.skipped_duplicates} duplicates skipped, "
          f"{result.claimants_created} claimants created, classified_by={result.classified_by}, "
          f"{len(result.errors)} errors)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claims", type=int, default=20000)
    parser.add_argument("--years", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/claims/synthetic_claims.csv"))
    parser.add_argument("--load", action="store_true", help="Also import the CSV into DATABASE_URL")
    args = parser.parse_args()

    rows = generate(args.claims, args.years, args.seed)
    write_csv(rows, args.out)
    print(f"Wrote {len(rows)} claims to {args.out}")
    if args.load:
        asyncio.run(load(args.out))


if __name__ == "__main__":
    main()
