"""
Loads historical claim records from CSV into claimants + claims.

One CSV row = one claim, with the claimant's background repeated on each of
their claims (that's how insurer/TPA extracts usually arrive). Claimants are
de-duplicated on claimant_ref and claims on claim_no, so re-importing the same
or an overlapping extract is safe.

Expected columns (header row required; only claim_no, claimant_ref,
claim_amount, filed_date and status are mandatory):
    claim_no, claimant_ref, age, gender, occupation, annual_income, city_tier,
    state, pre_existing_conditions, policy_tenure_years, prior_claims_count,
    purchase_channel, insurer_name, policy_type, claim_type, claim_amount,
    settled_amount, filed_date, decision_date, status, decision_reason_text,
    reason_category
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claim_reasons import classify_by_rules, classify_with_llm, taxonomy_for
from app.models.claim import Claim, Claimant, ClaimStatus

REQUIRED_COLUMNS = {"claim_no", "claimant_ref", "claim_amount", "filed_date", "status"}
LLM_BATCH_SIZE = 50
_STATUSES = {s.value for s in ClaimStatus}


@dataclass
class ImportResult:
    inserted: int = 0
    skipped_duplicates: int = 0
    claimants_created: int = 0
    classified_by: dict[str, int] = field(default_factory=lambda: {"source": 0, "rule": 0, "llm": 0})
    errors: list[dict] = field(default_factory=list)


def _blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _opt_float(value: str | None) -> float | None:
    return None if _blank(value) else float(value)


def _opt_int(value: str | None) -> int | None:
    return None if _blank(value) else int(float(value))


def _opt_date(value: str | None) -> date | None:
    return None if _blank(value) else date.fromisoformat(value.strip())


def _opt_bool(value: str | None) -> bool | None:
    if _blank(value):
        return None
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _opt_str(value: str | None) -> str | None:
    return None if _blank(value) else value.strip()


def _claimant_fields(row: dict) -> dict:
    return {
        "age": _opt_int(row.get("age")),
        "gender": _opt_str(row.get("gender")),
        "occupation": _opt_str(row.get("occupation")),
        "annual_income": _opt_float(row.get("annual_income")),
        "city_tier": _opt_str(row.get("city_tier")),
        "state": _opt_str(row.get("state")),
        "pre_existing_conditions": _opt_bool(row.get("pre_existing_conditions")),
        "policy_tenure_years": _opt_float(row.get("policy_tenure_years")),
        "prior_claims_count": _opt_int(row.get("prior_claims_count")),
        "purchase_channel": _opt_str(row.get("purchase_channel")),
    }


async def import_claims_csv(db: AsyncSession, content: str, use_llm: bool = True) -> ImportResult:
    result = ImportResult()
    reader = csv.DictReader(io.StringIO(content))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        result.errors.append({"row": 1, "error": f"Missing required columns: {sorted(missing)}"})
        return result

    rows = list(reader)
    claim_nos = {r["claim_no"].strip() for r in rows if not _blank(r.get("claim_no"))}
    refs = {r["claimant_ref"].strip() for r in rows if not _blank(r.get("claimant_ref"))}

    existing_claims = set((await db.execute(
        select(Claim.claim_no).where(Claim.claim_no.in_(claim_nos))
    )).scalars().all()) if claim_nos else set()
    claimants: dict[str, Claimant] = {
        c.external_ref: c for c in (await db.execute(
            select(Claimant).where(Claimant.external_ref.in_(refs))
        )).scalars().all()
    } if refs else {}

    unclassified: dict[str, list[Claim]] = {}
    seen_in_file: set[str] = set()

    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        try:
            claim_no = row["claim_no"].strip()
            ref = row["claimant_ref"].strip()
            status = row["status"].strip().lower()
            if not claim_no or not ref:
                raise ValueError("claim_no and claimant_ref are required")
            if status not in _STATUSES:
                raise ValueError(f"status must be one of {sorted(_STATUSES)}")
            if claim_no in existing_claims or claim_no in seen_in_file:
                result.skipped_duplicates += 1
                continue

            claimant = claimants.get(ref)
            if claimant is None:
                claimant = Claimant(external_ref=ref, **_claimant_fields(row))
                db.add(claimant)
                claimants[ref] = claimant
                result.claimants_created += 1

            remark = _opt_str(row.get("decision_reason_text"))
            claim = Claim(
                claim_no=claim_no,
                claimant=claimant,
                insurer_name=_opt_str(row.get("insurer_name")),
                policy_type=_opt_str(row.get("policy_type")),
                claim_type=_opt_str(row.get("claim_type")),
                claim_amount=float(row["claim_amount"]),
                settled_amount=_opt_float(row.get("settled_amount")),
                filed_date=_opt_date(row["filed_date"]),
                decision_date=_opt_date(row.get("decision_date")),
                status=status,
                decision_reason_text=remark,
            )
        except (ValueError, KeyError) as exc:
            result.errors.append({"row": line_no, "error": str(exc)})
            continue

        given = _opt_str(row.get("reason_category"))
        if given and status != "pending" and given in taxonomy_for(status):
            claim.reason_category, claim.reason_classified_by = given, "source"
            result.classified_by["source"] += 1
        elif (category := classify_by_rules(status, remark)) is not None:
            claim.reason_category, claim.reason_classified_by = category, "rule"
            result.classified_by["rule"] += 1
        elif status != "pending" and remark:
            unclassified.setdefault(status, []).append(claim)
        elif status != "pending":
            claim.reason_category, claim.reason_classified_by = "other", "rule"
            result.classified_by["rule"] += 1

        db.add(claim)
        seen_in_file.add(claim_no)
        result.inserted += 1

    for status, claims in unclassified.items():
        for start in range(0, len(claims), LLM_BATCH_SIZE):
            batch = claims[start:start + LLM_BATCH_SIZE]
            if use_llm:
                categories = await classify_with_llm(status, [c.decision_reason_text for c in batch])
                method = "llm"
            else:
                categories, method = ["other"] * len(batch), "rule"
            for claim, category in zip(batch, categories):
                claim.reason_category, claim.reason_classified_by = category, method
                result.classified_by[method] += 1

    await db.commit()
    return result
