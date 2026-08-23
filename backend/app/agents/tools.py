"""Agent tools. Every tool reads the database through repositories/services -
the agent layer can never fabricate a number."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.baseline import options_from_opportunities, _split
from app.analytics.metrics import failure_reasons as failure_reasons_metric
from app.analytics.metrics import payment_method_performance
from app.analytics.metrics import revenue_metrics
from app.models import RecoveryOpportunity, Transaction
from app.repositories import customer_repository, opportunity_repository, transaction_repository


# --------------------------------------------------------------------------- #
def get_revenue_metrics(db: Session, days: int = 30) -> dict:
    m = revenue_metrics(db, days=days)
    return {
        "period_days": days,
        "total_revenue": m["total_revenue"],
        "successful_revenue": m["successful_revenue"],
        "failed_transaction_value": m["failed_transaction_value"],
        "revenue_at_risk": m["revenue_at_risk"],
        "potential_recoverable_revenue": m["potential_recoverable_revenue"],
        "failure_rate": m["failure_rate"],
        "recovery_rate": m["recovery_rate"],
        "failed_count": m["failed_count"],
        "total_transactions": m["total_transactions"],
        "vs_previous_period_pct": {
            k: v["delta_pct"] for k, v in m["comparison"].items() if k in ("revenue_at_risk", "potential_recoverable_revenue", "failure_rate")
        },
    }


def get_failed_transactions(
    db: Session,
    *,
    limit: int = 10,
    min_amount: float | None = None,
    payment_method: str | None = None,
) -> list[dict]:
    txns, total = transaction_repository.list_transactions(
        db,
        status="FAILED,ABANDONED",
        payment_method=payment_method,
        min_amount=min_amount,
        sort="amount",
        size=limit,
    )
    return [
        {
            "transaction_id": t.transaction_id,
            "customer_id": t.customer.external_customer_id,
            "customer_name": t.customer.name,
            "amount": t.amount,
            "status": t.status,
            "payment_method": t.payment_method,
            "failure_code": t.failure_code or ("abandoned_checkout" if t.status == "ABANDONED" else None),
            "attempts": t.attempt_count,
            "created_at": str(t.created_at),
        }
        for t in txns
    ], total


def get_recovery_opportunities(db: Session, *, priority: str | None = None, limit: int = 5) -> list[dict]:
    opps, _ = opportunity_repository.list_opportunities(
        db, priority=priority, sort="expected_recovery_value", size=limit
    )
    return [
        {
            "opportunity_id": o.id,
            "customer_name": o.customer.name,
            "customer_id": o.customer.external_customer_id,
            "amount_at_risk": o.revenue_at_risk,
            "recovery_probability": o.recovery_probability,
            "expected_recovery_value": o.expected_recovery_value,
            "score": o.recovery_score,
            "priority": o.priority,
            "sub_cause": o.sub_cause,
            "recommended_action": o.recommended_action,
            "attempts": o.transaction.attempt_count,
        }
        for o in opps
    ]


def analyze_customer(db: Session, customer_id: str) -> dict | None:
    customer = customer_repository.get_by_external_id(db, customer_id.strip())
    if customer is None:
        return None
    method_rows = db.execute(
        select(
            Transaction.payment_method,
            func.sum(case((Transaction.status == "SUCCESS", 1), else_=0)),
            func.count(),
        )
        .where(Transaction.customer_id == customer.id)
        .group_by(Transaction.payment_method)
    ).all()
    recent_txns, _ = transaction_repository.list_transactions(db, customer_external_id=customer.external_customer_id, size=6)
    open_opps, open_total = opportunity_repository.list_opportunities(
        db, customer_external_id=customer.external_customer_id, size=5
    )
    return {
        "customer": {
            "id": customer.external_customer_id,
            "name": customer.name,
            "segment": customer.segment,
            "lifetime_value": customer.lifetime_value,
            "successful_transactions": customer.successful_transactions,
            "failed_transactions": customer.failed_transactions,
        },
        "payment_methods": [
            {"method": m, "success_rate": (s or 0) / c if c else 0.0, "transactions": int(c)}
            for m, s, c in sorted(method_rows, key=lambda r: -int(r[2]))
        ],
        "recent_transactions": [
            {"transaction_id": t.transaction_id, "amount": t.amount, "status": t.status, "method": t.payment_method}
            for t in recent_txns
        ],
        "open_recovery_opportunities": [
            {
                "amount": o.revenue_at_risk,
                "probability": o.recovery_probability,
                "expected_recovery": o.expected_recovery_value,
                "priority": o.priority,
                "sub_cause": o.sub_cause,
            }
            for o in open_opps
        ],
    }


def analyze_payment_method(db: Session, method: str | None = None) -> list[dict] | dict | None:
    perf = payment_method_performance(db, days=None)
    if method:
        wanted = method.upper()
        for row in perf:
            if row["method"] == wanted:
                return row
        return None
    return perf


def calculate_recovery_value(db: Session, *, opportunity_id: int | None = None) -> dict | None:
    stmt = select(RecoveryOpportunity).where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
    if opportunity_id is not None:
        stmt = stmt.where(RecoveryOpportunity.id == opportunity_id)
    else:
        stmt = stmt.order_by(RecoveryOpportunity.expected_recovery_value.desc()).limit(1)
    opp = db.scalar(stmt)
    if opp is None:
        return None
    return {
        "opportunity_id": opp.id,
        "transaction_id": opp.transaction.transaction_id,
        "customer_name": opp.customer.name,
        "revenue_at_risk": opp.revenue_at_risk,
        "recovery_probability": opp.recovery_probability,
        "expected_recovery_value": opp.expected_recovery_value,
        "formula": "expected_recovery_value = revenue_at_risk x recovery_probability",
        "priority": opp.priority,
    }


def generate_recommendation_tool(db: Session, *, opportunity_id: int) -> dict | None:
    opp = opportunity_repository.get_by_id(db, opportunity_id)
    if opp is None:
        return None
    return {
        "opportunity_id": opp.id,
        "revenue_at_risk": opp.revenue_at_risk,
        "recovery_probability": opp.recovery_probability,
        "expected_recovery_value": opp.expected_recovery_value,
        "root_cause": opp.root_cause,
        "sub_cause": opp.sub_cause,
        "priority": opp.priority,
        "recommended_action": opp.recommended_action,
        "explanation": opp.explanation,
        "retry_policy": opp.retry_policy,
    }


def get_failure_reasons(db: Session, days: int | None = 30) -> list[dict]:
    rows = failure_reasons_metric(db, days=days)[:6]
    total_value = sum(r["value_at_risk"] for r in rows) or 1.0
    for r in rows:
        r["share_of_loss"] = round(r["value_at_risk"] / total_value, 4)
    return rows


def compare_weekly_recovery(db: Session) -> dict:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    windows = {}
    labels = ["this_week", "last_week"]
    for i, label in enumerate(labels):
        end = now - timedelta(days=7 * i)
        start = end - timedelta(days=7)
        stmt = (
            select(RecoveryOpportunity)
            .join(Transaction, RecoveryOpportunity.transaction_id == Transaction.id)
            .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
            .where(Transaction.created_at >= start, Transaction.created_at < end)
        )
        opps = list(db.scalars(stmt).all())
        split = _split(options_from_opportunities(opps))
        windows[label] = {
            "revenue_at_risk": split["revenue_at_risk"],
            "ai_assisted_recovery_rate": split["ai_assisted_recovery_rate"],
            "ai_assisted_recovered_revenue": split["ai_assisted_recovered_revenue"],
            "baseline_recovery_rate": split["baseline_recovery_rate"],
        }
    delta_rate = (
        (windows["this_week"]["ai_assisted_recovery_rate"] - windows["last_week"]["ai_assisted_recovery_rate"])
        * 100
    )
    windows["rate_change_pp"] = round(delta_rate, 2)
    return windows


TOOL_HANDLERS = {
    "get_revenue_metrics": get_revenue_metrics,
    "get_failed_transactions": get_failed_transactions,
    "get_recovery_opportunities": get_recovery_opportunities,
    "analyze_customer": analyze_customer,
    "analyze_payment_method": analyze_payment_method,
    "calculate_recovery_value": calculate_recovery_value,
    "generate_recommendation": generate_recommendation_tool,
    "get_failure_reasons": get_failure_reasons,
    "compare_weekly_recovery": compare_weekly_recovery,
}
