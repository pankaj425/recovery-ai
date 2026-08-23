"""Revenue analytics: metrics, trends, failure reasons, payment methods.

All figures are OBSERVED FACTS aggregated via SQL; anything derived from the
model is clearly prefixed with `estimated_`/`potential_`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Customer, RecoveryOpportunity, Transaction


def _window(days: int | None) -> tuple[datetime | None, datetime]:
    now = datetime.now(timezone.utc)
    if days is None:
        return None, now
    return now - timedelta(days=days), now


def _status_sums(db: Session, start: datetime | None, end: datetime) -> dict:
    stmt = select(
        func.count(),
        func.coalesce(func.sum(Transaction.amount), 0.0),
        func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)),
        func.coalesce(func.sum(case((Transaction.status == "SUCCESS", Transaction.amount), else_=0.0)), 0.0),
        func.sum(case((Transaction.status == "FAILED", 1), else_=0)),
        func.coalesce(func.sum(case((Transaction.status == "FAILED", Transaction.amount), else_=0.0)), 0.0),
        func.sum(case((Transaction.status == "ABANDONED", 1), else_=0)),
        func.coalesce(func.sum(case((Transaction.status == "ABANDONED", Transaction.amount), else_=0.0)), 0.0),
        func.sum(case((Transaction.status == "PENDING", 1), else_=0)),
        func.coalesce(func.sum(case((Transaction.status == "PENDING", Transaction.amount), else_=0.0)), 0.0),
        func.sum(case((Transaction.status == "REFUNDED", 1), else_=0)),
        func.coalesce(func.sum(case((Transaction.status == "REFUNDED", Transaction.amount), else_=0.0)), 0.0),
    ).where(Transaction.created_at <= end)
    if start is not None:
        stmt = stmt.where(Transaction.created_at >= start)

    (
        total_count,
        total_value,
        success_count,
        success_value,
        failed_count,
        failed_value,
        abandoned_count,
        abandoned_value,
        pending_count,
        pending_value,
        refunded_count,
        refunded_value,
    ) = db.execute(stmt).one()

    at_risk_value = float(failed_value or 0) + float(abandoned_value or 0)
    decided_count = int(success_count or 0) + int(failed_count or 0)
    return {
        "total_transactions": int(total_count or 0),
        "total_revenue": round(float(total_value or 0), 2),
        "successful_revenue": round(float(success_value or 0), 2),
        "failed_transaction_value": round(float(failed_value or 0), 2),
        "abandoned_value": round(float(abandoned_value or 0), 2),
        "pending_value": round(float(pending_value or 0), 2),
        "refunded_value": round(float(refunded_value or 0), 2),
        "revenue_at_risk": round(at_risk_value, 2),
        "success_count": int(success_count or 0),
        "failed_count": int(failed_count or 0),
        "failure_rate": round(int(failed_count or 0) / decided_count, 4) if decided_count else 0.0,
        "average_transaction_value": round(float(total_value or 0) / total_count, 2) if total_count else 0.0,
    }


def revenue_metrics(db: Session, days: int = 30) -> dict:
    """KPI block with previous-period comparison."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    current = _status_sums(db, start, now)
    previous = _status_sums(db, prev_start, start)

    # Potential recoverable = SUM(expected_recovery_value) for open opportunities
    # tied to transactions created inside the window (model-derived).
    open_expected = db.scalar(
        select(func.coalesce(func.sum(RecoveryOpportunity.expected_recovery_value), 0.0))
        .join(Transaction, RecoveryOpportunity.transaction_id == Transaction.id)
        .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
        .where(Transaction.created_at >= start)
    ) or 0.0
    current["potential_recoverable_revenue"] = round(float(open_expected), 2)
    current["recovery_rate"] = (
        round(current["potential_recoverable_revenue"] / current["revenue_at_risk"], 4)
        if current["revenue_at_risk"]
        else 0.0
    )

    prev_open_expected = db.scalar(
        select(func.coalesce(func.sum(RecoveryOpportunity.expected_recovery_value), 0.0))
        .join(Transaction, RecoveryOpportunity.transaction_id == Transaction.id)
        .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
        .where(Transaction.created_at < start, Transaction.created_at >= prev_start)
    ) or 0.0
    previous["potential_recoverable_revenue"] = round(float(prev_open_expected), 2)
    previous["recovery_rate"] = (
        round(previous["potential_recoverable_revenue"] / previous["revenue_at_risk"], 4)
        if previous["revenue_at_risk"]
        else 0.0
    )

    comparison_fields = [
        "total_revenue",
        "successful_revenue",
        "failed_transaction_value",
        "revenue_at_risk",
        "potential_recoverable_revenue",
        "recovery_rate",
        "failure_rate",
        "average_transaction_value",
    ]
    trends = {
        f: {
            "current": current[f],
            "previous": previous[f],
            "delta_pct": round(
                (current[f] - previous[f]) / previous[f] * 100, 2
            )
            if isinstance(current[f], (int, float)) and previous[f]
            else None,
        }
        for f in comparison_fields
    }
    return {"period_days": days, **{k: v for k, v in current.items()}, "comparison": trends}


def daily_trends(db: Session, days: int = 30) -> list[dict]:
    start, _ = _window(days)
    day = func.date(Transaction.created_at).label("day")
    stmt = (
        select(
            day,
            func.count(),
            func.coalesce(func.sum(Transaction.amount), 0.0),
            func.coalesce(func.sum(case((Transaction.status == "SUCCESS", Transaction.amount), else_=0.0)), 0.0),
            func.coalesce(func.sum(case((Transaction.status.in_(("FAILED", "ABANDONED")), Transaction.amount), else_=0.0)), 0.0),
            func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)),
            func.sum(case((Transaction.status.in_(("FAILED", "ABANDONED")), 1), else_=0)),
        )
        .group_by(day)
        .order_by(day)
    )
    if start is not None:
        stmt = stmt.where(Transaction.created_at >= start)
    rows = db.execute(stmt).all()
    return [
        {
            "date": str(row.day),
            "transactions": int(row[1]),
            "volume": round(float(row[2]), 2),
            "successful_value": round(float(row[3]), 2),
            "at_risk_value": round(float(row[4]), 2),
            "successful_count": int(row[5] or 0),
            "failed_count": int(row[6] or 0),
        }
        for row in rows
    ]


def failure_reasons(db: Session, days: int | None = None) -> list[dict]:
    """Failure codes with count, value at risk and model-estimated recoverable value."""
    start, _ = _window(days)
    base = select(
        Transaction.failure_code,
        func.count(),
        func.coalesce(func.sum(Transaction.amount), 0.0),
    ).where(Transaction.status.in_(("FAILED", "ABANDONED")))
    if start is not None:
        base = base.where(Transaction.created_at >= start)
    rows = db.execute(base.group_by(Transaction.failure_code)).all()

    recoverable_stmt = (
        select(
            Transaction.failure_code,
            func.coalesce(func.sum(RecoveryOpportunity.expected_recovery_value), 0.0),
        )
        .join(RecoveryOpportunity, RecoveryOpportunity.transaction_id == Transaction.id)
        .group_by(Transaction.failure_code)
    )
    recoverable = {code: float(val) for code, val in db.execute(recoverable_stmt).all()}

    items = []
    for code, count, value in rows:
        items.append(
            {
                "code": code or "abandoned_checkout",
                "count": int(count),
                "value_at_risk": round(float(value), 2),
                "estimated_recoverable": round(recoverable.get(code, 0.0), 2),
            }
        )
    return sorted(items, key=lambda i: i["value_at_risk"], reverse=True)


def payment_method_performance(db: Session, days: int | None = None) -> list[dict]:
    start, _ = _window(days)
    conditions = [Transaction.status.in_(("SUCCESS", "FAILED", "ABANDONED"))]
    if start is not None:
        conditions.append(Transaction.created_at >= start)

    rows = db.execute(
        select(
            Transaction.payment_method,
            func.count(),
            func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)),
            func.coalesce(func.sum(case((Transaction.status == "SUCCESS", Transaction.amount), else_=0.0)), 0.0),
            func.coalesce(func.sum(case((Transaction.status.in_(("FAILED", "ABANDONED")), Transaction.amount), else_=0.0)), 0.0),
        )
        .where(*conditions)
        .group_by(Transaction.payment_method)
    ).all()

    lost_stmt = select(
        Transaction.payment_method,
        func.coalesce(func.sum(RecoveryOpportunity.expected_recovery_value), 0.0),
    ).join(RecoveryOpportunity, RecoveryOpportunity.transaction_id == Transaction.id)
    if start is not None:
        lost_stmt = lost_stmt.where(Transaction.created_at >= start)
    estimated_recovered = {m: float(v) for m, v in db.execute(lost_stmt.group_by(Transaction.payment_method)).all()}

    items = []
    for method, count, succeeded, success_value, failed_value in rows:
        total = int(count)
        ok = int(succeeded or 0)
        items.append(
            {
                "method": method,
                "transactions": total,
                "success_rate": round(ok / total, 4) if total else 0.0,
                "failure_rate": round((total - ok) / total, 4) if total else 0.0,
                "successful_volume": round(float(success_value), 2),
                "revenue_lost": round(float(failed_value), 2),
                "estimated_recoverable": round(estimated_recovered.get(method, 0.0), 2),
            }
        )
    return sorted(items, key=lambda i: i["revenue_lost"], reverse=True)


def priority_distribution(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            RecoveryOpportunity.priority,
            func.count(),
            func.coalesce(func.sum(RecoveryOpportunity.revenue_at_risk), 0.0),
            func.coalesce(func.sum(RecoveryOpportunity.expected_recovery_value), 0.0),
        )
        .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
        .group_by(RecoveryOpportunity.priority)
    ).all()
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return [
        {
            "priority": p,
            "count": int(c),
            "value_at_risk": round(float(v), 2),
            "expected_recovery": round(float(e), 2),
        }
        for p, c, v, e in sorted(rows, key=lambda r: order.get(r[0], 9))
    ]


def customer_segments(db: Session) -> list[dict]:
    rows = db.execute(
        select(Customer.segment, func.count(), func.coalesce(func.sum(Customer.lifetime_value), 0.0))
        .group_by(Customer.segment)
    ).all()
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return [
        {"segment": s or "LOW", "customers": int(c), "lifetime_value": round(float(l), 2)}
        for s, c, l in sorted(rows, key=lambda r: order.get(r[0] or "LOW", 9))
    ]
