from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.models import Customer, PaymentAttempt, Transaction


def get_by_transaction_id(db: Session, transaction_id: str) -> Transaction | None:
    return db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))


def add_attempt(
    db: Session,
    transaction: Transaction,
    *,
    attempt_number: int,
    payment_method: str,
    status: str = "FAILED",
    failure_code: str | None = None,
    failure_reason: str | None = None,
    timestamp: datetime | None = None,
) -> PaymentAttempt:
    attempt = PaymentAttempt(
        transaction_id=transaction.id,
        attempt_number=attempt_number,
        payment_method=payment_method,
        status=status,
        failure_code=failure_code,
        failure_reason=failure_reason,
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    db.add(attempt)
    return attempt


_SORTABLE = {
    "created_at": Transaction.created_at,
    "amount": Transaction.amount,
    "attempt_count": Transaction.attempt_count,
}


def list_transactions(
    db: Session,
    *,
    status: str | None = None,
    payment_method: str | None = None,
    failure_code: str | None = None,
    customer_external_id: str | None = None,
    min_amount: float | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    size: int = 25,
) -> tuple[list[Transaction], int]:
    stmt: Select = select(Transaction)
    if status:
        stmt = stmt.where(Transaction.status.in_([s.upper() for s in status.split(",")]))
    if payment_method:
        stmt = stmt.where(Transaction.payment_method == payment_method.upper())
    if failure_code:
        stmt = stmt.where(Transaction.failure_code == failure_code.lower())
    if customer_external_id:
        stmt = stmt.join(Customer, Transaction.customer_id == Customer.id).where(
            Customer.external_customer_id == customer_external_id
        )
    if min_amount is not None:
        stmt = stmt.where(Transaction.amount >= min_amount)
    if search:
        stmt = stmt.where(Transaction.transaction_id.ilike(f"%{search}%"))
    if date_from:
        stmt = stmt.where(Transaction.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.created_at <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = _SORTABLE.get(sort, Transaction.created_at)
    stmt = stmt.order_by(col.desc() if order.lower() != "asc" else col.asc())
    items = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return list(items), int(total)


def method_success_rates(db: Session) -> dict[str, float]:
    """Payment method -> historical success rate across SUCCESS/FAILED txns."""
    successes = func.sum(case((Transaction.status == "SUCCESS", 1), else_=0))
    rows = db.execute(
        select(Transaction.payment_method, successes, func.count())
        .where(Transaction.status.in_(("SUCCESS", "FAILED")))
        .group_by(Transaction.payment_method)
    ).all()
    DEFAULT_RATE = 0.6
    rates: dict[str, float] = {}
    for method, succeeded, total in rows:
        rates[method] = (succeeded or 0) / total if total else DEFAULT_RATE
    return rates
