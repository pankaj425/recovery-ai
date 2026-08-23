from __future__ import annotations

from fastapi import APIRouter, Query

from app.analytics import baseline as baseline_analytics
from app.analytics import metrics as analytics
from app.api.deps import CurrentUser, DBSession

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/revenue", summary="Dashboard KPI metrics with previous-period comparison")
def revenue(db: DBSession, user: CurrentUser, days: int = Query(default=30, ge=1, le=365)) -> dict:
    return {"success": True, "data": analytics.revenue_metrics(db, days=days)}


@router.get("/trends", summary="Daily revenue / risk trend series")
def trends(db: DBSession, user: CurrentUser, days: int = Query(default=30, ge=1, le=365)) -> dict:
    return {"success": True, "data": analytics.daily_trends(db, days=days)}


@router.get("/failure-reasons", summary="Failure codes ranked by value at risk")
def failure_reasons(
    db: DBSession,
    user: CurrentUser,
    days: int | None = Query(default=None, ge=1, le=365),
) -> dict:
    return {"success": True, "data": analytics.failure_reasons(db, days=days)}


@router.get("/payment-methods", summary="Payment-method performance")
def payment_methods(
    db: DBSession,
    user: CurrentUser,
    days: int | None = Query(default=None, ge=1, le=365),
) -> dict:
    return {"success": True, "data": analytics.payment_method_performance(db, days=days)}


@router.get("/priorities", summary="Open opportunity distribution by priority")
def priorities(db: DBSession, user: CurrentUser) -> dict:
    return {"success": True, "data": analytics.priority_distribution(db)}


@router.get("/segments", summary="Customer value segments")
def segments(db: DBSession, user: CurrentUser) -> dict:
    return {"success": True, "data": analytics.customer_segments(db)}


@router.get("/recovered-revenue", summary="Baseline vs AI-assisted recovered revenue (whole book)")
def recovered_revenue(db: DBSession, user: CurrentUser, days: int | None = None) -> dict:
    summary = baseline_analytics.recovered_revenue_summary(db, days=days)
    summary["recovery_rate"] = summary["ai_assisted_recovery_rate"]
    summary["baseline_recovery_rate_pct"] = round(summary["baseline_recovery_rate"] * 100, 2)
    summary["ai_recovery_rate_pct"] = round(summary["ai_assisted_recovery_rate"] * 100, 2)
    return {"success": True, "data": summary}


@router.get("/baseline-comparison", summary="Rule-based dunning vs RecoveryAI on top opportunities cohort")
def baseline_comparison(db: DBSession, user: CurrentUser, sample_size: int = Query(default=100, ge=10, le=1000)) -> dict:
    return {"success": True, "data": baseline_analytics.baseline_comparison(db, sample_size=sample_size)}
