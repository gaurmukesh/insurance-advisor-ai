"""
Settlement analytics over historical claims.

All numbers here are computed deterministically from the claims table -- the
LLM is only used afterwards (explain_findings) to put already-computed
aggregates into plain language. It never sees individual claim or claimant
rows, and it never decides what the counts or correlations are.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta

from scipy.stats import chi2_contingency, pointbiserialr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claim_reasons import APPROVAL_REASONS, REJECTION_REASONS
from app.core.llm import chat
from app.models.claim import Claim, Claimant

APPROVED_STATUSES = ("approved", "partially_approved")
DECIDED_STATUSES = (*APPROVED_STATUSES, "rejected")
LOW_SAMPLE_THRESHOLD = 30

CORRELATION_CAVEAT = (
    "These are associations in historical data, not causes. A background attribute "
    "that correlates with rejection usually does so through a reason (e.g. pre-existing "
    "conditions -> non-disclosure), so read each attribute alongside its top rejection "
    "reason. Protected attributes such as gender are reported for fairness auditing and "
    "must not be used as inputs to claim decisions."
)


@dataclass(frozen=True)
class Period:
    since: date
    until: date

    @classmethod
    def last_months(cls, months: int, today: date | None = None) -> "Period":
        today = today or date.today()
        return cls(since=today - timedelta(days=round(months * 30.4375)), until=today)

    def as_dict(self) -> dict:
        return {"since": self.since.isoformat(), "until": self.until.isoformat()}


# ── 1 & 2: primary rejection / approval reasons ─────────────────────────────

async def reason_breakdown(db: AsyncSession, outcome: str, period: Period) -> dict:
    """outcome is 'rejected' or 'approved' (approved includes partially_approved).
    Claims are placed in the period by decision_date -- the question is about
    settlements decided in that window, not claims filed in it."""
    statuses = ("rejected",) if outcome == "rejected" else APPROVED_STATUSES
    taxonomy = REJECTION_REASONS if outcome == "rejected" else APPROVAL_REASONS
    in_period = (Claim.decision_date >= period.since, Claim.decision_date <= period.until)

    total_decided = (await db.execute(
        select(func.count(Claim.id)).where(Claim.status.in_(DECIDED_STATUSES), *in_period)
    )).scalar_one()

    rows = (await db.execute(
        select(
            func.coalesce(Claim.reason_category, "other").label("category"),
            func.count(Claim.id).label("count"),
            func.sum(Claim.claim_amount).label("claimed"),
            func.sum(Claim.settled_amount).label("settled"),
        )
        .where(Claim.status.in_(statuses), *in_period)
        .group_by("category")
        .order_by(func.count(Claim.id).desc())
    )).all()

    total = sum(r.count for r in rows)
    reasons = [{
        "category": r.category,
        "description": taxonomy.get(r.category, r.category),
        "count": r.count,
        "share_pct": round(r.count / total * 100, 1) if total else 0.0,
        "total_claimed_amount": round(r.claimed or 0, 2),
        "total_settled_amount": round(r.settled or 0, 2),
    } for r in rows]

    # "other" is a catch-all, not an answer -- report the top named reason as
    # primary, and only fall back to "other" if nothing else exists.
    named = [r for r in reasons if r["category"] != "other"]
    return {
        "outcome": outcome,
        "period": period.as_dict(),
        "total_decided_claims": total_decided,
        "claims_in_outcome": total,
        "outcome_rate_pct": round(total / total_decided * 100, 1) if total_decided else 0.0,
        "primary_reason": (named or reasons or [None])[0],
        "reasons": reasons,
    }


# ── 3: rejection vs claimant background ─────────────────────────────────────

def _age_bucket(v):
    return None if v is None else "<30" if v < 30 else "30-44" if v < 45 else "45-59" if v < 60 else "60+"


def _income_bucket(v):
    if v is None:
        return None
    for limit, label in ((300_000, "<3L"), (600_000, "3-6L"), (1_200_000, "6-12L"), (2_500_000, "12-25L")):
        if v < limit:
            return label
    return "25L+"


def _tenure_bucket(v):
    return None if v is None else "<1y" if v < 1 else "1-2y" if v < 2 else "2-4y" if v < 4 else "4y+"


def _prior_claims_bucket(v):
    return None if v is None else str(v) if v < 3 else "3+"


def _bool_bucket(v):
    return None if v is None else "yes" if v else "no"


def _as_is(v):
    return v or None


# attribute -> (bucketing function, is_numeric). Numeric attributes also get a
# point-biserial correlation on the raw value, alongside the bucketed test.
BACKGROUND_ATTRIBUTES = {
    "age": (_age_bucket, True),
    "annual_income": (_income_bucket, True),
    "policy_tenure_years": (_tenure_bucket, True),
    "prior_claims_count": (_prior_claims_bucket, True),
    "pre_existing_conditions": (_bool_bucket, False),
    "gender": (_as_is, False),
    "occupation": (_as_is, False),
    "city_tier": (_as_is, False),
    "state": (_as_is, False),
    "purchase_channel": (_as_is, False),
}


def _strength(v: float | None) -> str:
    if v is None:
        return "insufficient_data"
    return "negligible" if v < 0.1 else "weak" if v < 0.2 else "moderate" if v < 0.3 else "strong"


def compute_rejection_correlation(records: list[dict]) -> dict:
    """records: one dict per decided claim with the BACKGROUND_ATTRIBUTES
    keys, plus 'rejected' (bool) and 'reason_category'. Pure function so it
    can be tested without a database."""
    n = len(records)
    overall_rejected = sum(r["rejected"] for r in records)
    overall_rate = overall_rejected / n if n else 0.0

    attributes = []
    for name, (bucket_fn, numeric) in BACKGROUND_ATTRIBUTES.items():
        buckets: dict[str, dict] = {}
        unknown = 0
        for r in records:
            label = bucket_fn(r.get(name))
            if label is None:
                unknown += 1
                continue
            b = buckets.setdefault(label, {"claims": 0, "rejected": 0, "reasons": {}})
            b["claims"] += 1
            if r["rejected"]:
                b["rejected"] += 1
                reason = r.get("reason_category") or "other"
                b["reasons"][reason] = b["reasons"].get(reason, 0) + 1

        bucket_rows = []
        for label, b in buckets.items():
            rate = b["rejected"] / b["claims"]
            top_reason = max(b["reasons"].items(), key=lambda kv: kv[1])[0] if b["reasons"] else None
            bucket_rows.append({
                "value": label,
                "claims": b["claims"],
                "rejected": b["rejected"],
                "rejection_rate_pct": round(rate * 100, 1),
                "lift_vs_overall": round(rate / overall_rate, 2) if overall_rate else None,
                "top_rejection_reason": top_reason,
                "low_sample": b["claims"] < LOW_SAMPLE_THRESHOLD,
            })
        bucket_rows.sort(key=lambda b: b["rejection_rate_pct"], reverse=True)

        chi2 = p_value = cramers_v = None
        known = sum(b["claims"] for b in buckets.values())
        rejected_known = sum(b["rejected"] for b in buckets.values())
        # A 2xk test needs >= 2 groups and both outcomes present, otherwise a
        # row/column of the contingency table is all zeros and it's undefined.
        if len(buckets) >= 2 and 0 < rejected_known < known:
            table = [[b["rejected"], b["claims"] - b["rejected"]] for b in buckets.values()]
            chi2, p_value, _, _ = chi2_contingency(table)
            cramers_v = (chi2 / known) ** 0.5  # min(rows, cols) - 1 == 1 for a 2xk table

        point_biserial = None
        if numeric:
            pairs = [(float(r[name]), int(r["rejected"])) for r in records if r.get(name) is not None]
            outcomes = {o for _, o in pairs}
            values = {v for v, _ in pairs}
            if len(pairs) >= 3 and len(outcomes) == 2 and len(values) > 1:
                corr, pb_p = pointbiserialr([o for _, o in pairs], [v for v, _ in pairs])
                point_biserial = {"r": round(float(corr), 3), "p_value": float(pb_p)}

        attributes.append({
            "attribute": name,
            "cramers_v": round(cramers_v, 3) if cramers_v is not None else None,
            "strength": _strength(cramers_v),
            "chi2": round(float(chi2), 2) if chi2 is not None else None,
            "p_value": float(p_value) if p_value is not None else None,
            "significant": bool(p_value is not None and p_value < 0.05),
            "point_biserial": point_biserial,
            "unknown_count": unknown,
            "buckets": bucket_rows,
        })

    attributes.sort(key=lambda a: a["cramers_v"] if a["cramers_v"] is not None else -1, reverse=True)
    return {
        "decided_claims": n,
        "rejected_claims": overall_rejected,
        "overall_rejection_rate_pct": round(overall_rate * 100, 1),
        "strongest_factors": [
            a["attribute"] for a in attributes
            if a["significant"] and a["strength"] in ("weak", "moderate", "strong")
        ][:3],
        "attributes": attributes,
        "caveat": CORRELATION_CAVEAT,
    }


async def rejection_correlation(db: AsyncSession, period: Period) -> dict:
    rows = (await db.execute(
        select(Claim.status, Claim.reason_category, Claimant)
        .join(Claimant, Claimant.id == Claim.claimant_id)
        .where(
            Claim.status.in_(DECIDED_STATUSES),
            Claim.decision_date >= period.since,
            Claim.decision_date <= period.until,
        )
    )).all()
    records = [{
        **{attr: getattr(claimant, attr) for attr in BACKGROUND_ATTRIBUTES},
        "rejected": status == "rejected",
        "reason_category": reason,
    } for status, reason, claimant in rows]
    return {"period": period.as_dict(), **compute_rejection_correlation(records)}


async def settlement_overview(db: AsyncSession, period: Period) -> dict:
    """Year-by-year settlement ratio, for the long-run trend across all history."""
    year = func.extract("year", Claim.decision_date)
    rows = (await db.execute(
        select(
            year.label("year"),
            func.count(Claim.id).label("decided"),
            func.count(Claim.id).filter(Claim.status == "rejected").label("rejected"),
            func.sum(Claim.claim_amount).label("claimed"),
            func.sum(Claim.settled_amount).label("settled"),
        )
        .where(
            Claim.status.in_(DECIDED_STATUSES),
            Claim.decision_date >= period.since,
            Claim.decision_date <= period.until,
        )
        .group_by(year)
        .order_by(year)
    )).all()
    return {
        "period": period.as_dict(),
        "by_year": [{
            "year": int(r.year),
            "decided_claims": r.decided,
            "rejected_claims": r.rejected,
            "settlement_ratio_pct": round((r.decided - r.rejected) / r.decided * 100, 1),
            "amount_settlement_ratio_pct": round((r.settled or 0) / r.claimed * 100, 1) if r.claimed else 0.0,
        } for r in rows],
    }


# ── Plain-language narrative ─────────────────────────────────────────────────

_EXPLAIN_SYSTEM = (
    "You are a claims analytics expert for an Indian insurer. You are given "
    "pre-computed aggregate statistics as JSON. Explain the findings in 4-6 "
    "short bullet points for a claims manager. Use only numbers present in the "
    "JSON; do not invent figures. Flag low-sample buckets as tentative. Never "
    "suggest using gender or other protected attributes in claim decisions."
)


async def explain_findings(kind: str, payload: dict) -> str:
    # Trim per-bucket detail for the long-tail attributes: the narrative only
    # needs the top of each list, and it keeps the prompt small.
    slim = dict(payload)
    if "attributes" in slim:
        slim["attributes"] = [
            {**a, "buckets": a["buckets"][:4]} for a in slim["attributes"][:6]
        ]
    prompt = f"Analysis: {kind}\n\n{json.dumps(slim, default=str)}"
    return await chat(_EXPLAIN_SYSTEM, prompt, trace_name=f"explain_{kind}")
