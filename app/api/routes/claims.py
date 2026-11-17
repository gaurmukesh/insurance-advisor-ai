from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_advisor
from app.core.claims_analytics import (
    Period,
    explain_findings,
    reason_breakdown,
    rejection_correlation,
    settlement_overview,
)
from app.core.claims_ingest import import_claims_csv
from app.db.postgres import get_db
from app.models.advisor import Advisor

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _period(
    months: int = Query(12, ge=1, le=600, description="Look-back window ending today; ignored if since is given"),
    since: Optional[date] = Query(None),
    until: Optional[date] = Query(None),
) -> Period:
    if since is None:
        period = Period.last_months(months, today=until)
    else:
        period = Period(since=since, until=until or date.today())
    if period.since > period.until:
        raise HTTPException(status_code=422, detail="since must be on or before until")
    return period


async def _with_explanation(kind: str, payload: dict, explain: bool) -> dict:
    if explain:
        payload["explanation"] = await explain_findings(kind, payload)
    return payload


@router.post("/import")
async def import_claims(
    file: UploadFile = File(...),
    use_llm: bool = Query(True, description="Classify remarks no keyword rule matches with the LLM"),
    db: AsyncSession = Depends(get_db),
    current: Advisor = Depends(get_current_advisor),
):
    """Bulk-load historical claims from CSV. Restricted to manager/admin: it
    writes portfolio-wide data, not one advisor's own records."""
    if current.role not in ("manager", "admin"):
        raise HTTPException(status_code=403, detail="Only managers or admins can import claims")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV larger than 50 MB; split it into several imports")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded")
    result = await import_claims_csv(db, text, use_llm=use_llm)
    return {
        "inserted": result.inserted,
        "skipped_duplicates": result.skipped_duplicates,
        "claimants_created": result.claimants_created,
        "classified_by": result.classified_by,
        "errors": result.errors[:100],
        "error_count": len(result.errors),
    }


@router.get("/analysis/rejection-reasons")
async def rejection_reasons(
    period: Period = Depends(_period),
    explain: bool = False,
    db: AsyncSession = Depends(get_db),
    _current: Advisor = Depends(get_current_advisor),
):
    """Primary reason claims were rejected in the period (default: past 12 months)."""
    return await _with_explanation("rejection_reasons", await reason_breakdown(db, "rejected", period), explain)


@router.get("/analysis/approval-reasons")
async def approval_reasons(
    period: Period = Depends(_period),
    explain: bool = False,
    db: AsyncSession = Depends(get_db),
    _current: Advisor = Depends(get_current_advisor),
):
    """Primary reason claims were approved (fully or partially) in the period."""
    return await _with_explanation("approval_reasons", await reason_breakdown(db, "approved", period), explain)


@router.get("/analysis/rejection-correlation")
async def rejection_vs_background(
    period: Period = Depends(_period),
    explain: bool = False,
    db: AsyncSession = Depends(get_db),
    _current: Advisor = Depends(get_current_advisor),
):
    """How strongly each claimant background attribute is associated with rejection."""
    return await _with_explanation("rejection_correlation", await rejection_correlation(db, period), explain)


@router.get("/analysis/overview")
async def overview(
    period: Period = Depends(_period),
    db: AsyncSession = Depends(get_db),
    _current: Advisor = Depends(get_current_advisor),
):
    """Year-by-year settlement ratio. Pass a large `months` (or `since`) for the full history."""
    return await settlement_overview(db, period)
