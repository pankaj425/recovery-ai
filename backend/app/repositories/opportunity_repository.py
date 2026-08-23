from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import AIDecision, Customer, RecoveryOpportunity, ScoreAudit, Transaction


def get_by_id(db: Session, opportunity_id: int) -> RecoveryOpportunity | None:
    return db.get(RecoveryOpportunity, opportunity_id)


def get_by_transaction(db: Session, transaction_row_id: int) -> RecoveryOpportunity | None:
    return db.scalar(select(RecoveryOpportunity).where(RecoveryOpportunity.transaction_id == transaction_row_id))


_SORTABLE = {
    "recovery_score": RecoveryOpportunity.recovery_score,
    "expected_recovery_value": RecoveryOpportunity.expected_recovery_value,
    "revenue_at_risk": RecoveryOpportunity.revenue_at_risk,
    "created_at": RecoveryOpportunity.created_at,
    "recovery_probability": RecoveryOpportunity.recovery_probability,
}


def list_opportunities(
    db: Session,
    *,
    priority: str | None = None,
    status: str | None = None,
    min_amount: float | None = None,
    customer_external_id: str | None = None,
    root_cause: str | None = None,
    failure_code: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "recovery_score",
    order: str = "desc",
    page: int = 1,
    size: int = 20,
) -> tuple[list[RecoveryOpportunity], int]:
    stmt: Select = select(RecoveryOpportunity)
    if priority:
        stmt = stmt.where(RecoveryOpportunity.priority.in_([p.upper() for p in priority.split(",")]))
    if status:
        stmt = stmt.where(RecoveryOpportunity.status.in_([s.upper() for s in status.split(",")]))
    if min_amount is not None:
        stmt = stmt.where(RecoveryOpportunity.revenue_at_risk >= min_amount)
    if customer_external_id:
        stmt = stmt.join(Customer, RecoveryOpportunity.customer_id == Customer.id).where(
            Customer.external_customer_id == customer_external_id
        )
    if root_cause:
        stmt = stmt.where(RecoveryOpportunity.root_cause == root_cause.upper())
    if failure_code:
        stmt = stmt.join(Transaction, RecoveryOpportunity.transaction_id == Transaction.id).where(
            Transaction.failure_code == failure_code.lower()
        )
    if date_from:
        stmt = stmt.where(RecoveryOpportunity.created_at >= date_from)
    if date_to:
        stmt = stmt.where(RecoveryOpportunity.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = _SORTABLE.get(sort, RecoveryOpportunity.recovery_score)
    stmt = stmt.order_by(col.desc() if order.lower() != "asc" else col.asc())
    items = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return list(items), int(total)


def priority_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(RecoveryOpportunity.priority, func.count()).group_by(RecoveryOpportunity.priority)
    ).all()
    counts = {priority: count for priority, count in rows}
    return {level: counts.get(level, 0) for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}


def top_open_opportunities(db: Session, limit: int = 5) -> list[RecoveryOpportunity]:
    stmt = (
        select(RecoveryOpportunity)
        .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
        .order_by(RecoveryOpportunity.expected_recovery_value.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def open_opportunities_sample(db: Session, limit: int = 100) -> list[RecoveryOpportunity]:
    """Highest-value open opportunities - the simulation cohort."""
    return top_open_opportunities(db, limit=limit)


def record_audit(
    db: Session,
    *,
    opportunity: RecoveryOpportunity,
    score_breakdown: dict,
    weights: dict[str, float],
    features_snapshot: dict,
    prediction: dict,
    recommendation: dict,
    confidence: float,
    model_version: str,
) -> None:
    db.add(
        ScoreAudit(
            opportunity_id=opportunity.id,
            components=score_breakdown["components"],
            weights=weights,
            total_score=score_breakdown["total"],
        )
    )
    db.add(
        AIDecision(
            opportunity_id=opportunity.id,
            model_version=model_version,
            input_snapshot=features_snapshot,
            prediction=prediction,
            recommendation=recommendation,
            confidence=confidence,
        )
    )


def add_action(
    db: Session,
    *,
    opportunity_id: int,
    action_type: str,
    channel: str | None,
    status: str = "PENDING_APPROVAL",
    approved_by: str | None = None,
    result: dict | None = None,
):
    from app.models import RecoveryAction

    action = RecoveryAction(
        opportunity_id=opportunity_id,
        action_type=action_type,
        channel=channel,
        status=status,
        approved_by=approved_by,
        result=result,
    )
    db.add(action)
    db.flush()
    return action
