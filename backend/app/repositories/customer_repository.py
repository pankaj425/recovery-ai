from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Customer


def get_by_external_id(db: Session, external_customer_id: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.external_customer_id == external_customer_id))


def get_or_create(
    db: Session,
    *,
    external_customer_id: str,
    name: str | None = None,
    email: str | None = None,
) -> Customer:
    customer = get_by_external_id(db, external_customer_id)
    if customer is not None:
        if name and not customer.name.startswith("Customer"):
            pass  # keep richest known name
        elif name:
            customer.name = name
            customer.email = email or customer.email
        return customer
    customer = Customer(
        external_customer_id=external_customer_id,
        name=name or f"Customer {external_customer_id}",
        email=email or f"{external_customer_id.lower()}@example.com",
        segment="LOW",
        total_spend=0.0,
        lifetime_value=0.0,
    )
    db.add(customer)
    db.flush()
    return customer


def recompute_aggregates(db: Session, customer: Customer) -> Customer:
    """Refresh spend/LTV/success-failure counters from the transaction table."""
    from app.models import Transaction

    rows = db.execute(
        select(Transaction.status, func.count(), func.coalesce(func.sum(Transaction.amount), 0.0))
        .where(Transaction.customer_id == customer.id)
        .group_by(Transaction.status)
    ).all()
    totals = {status: (count, value) for status, count, value in rows}
    succeeded = totals.get("SUCCESS", (0, 0.0))
    failed = totals.get("FAILED", (0, 0.0))
    abandoned = totals.get("ABANDONED", (0, 0.0))
    refunded = totals.get("REFUNDED", (0, 0.0))

    customer.successful_transactions = succeeded[0]
    customer.failed_transactions = failed[0] + abandoned[0]
    customer.total_spend = round(succeeded[1] - refunded[1], 2)
    # LTV proxy: realized spend weighted by relationship length signal.
    customer.lifetime_value = round(max(customer.total_spend * 1.15, succeeded[1]), 2)

    total_txns = sum(count for count, _ in totals.values())
    if total_txns >= 20 and customer.total_spend >= 100_000:
        customer.segment = "HIGH"
    elif total_txns >= 5 and customer.total_spend >= 20_000:
        customer.segment = "MEDIUM"
    else:
        customer.segment = "LOW"
    return customer


def list_customers(
    db: Session,
    *,
    search: str | None = None,
    segment: str | None = None,
    page: int = 1,
    size: int = 25,
) -> tuple[list[Customer], int]:
    stmt = select(Customer)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.email.ilike(pattern), Customer.external_customer_id.ilike(pattern)))
    if segment:
        stmt = stmt.where(Customer.segment == segment.upper())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Customer.lifetime_value.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return list(items), int(total)


def monthly_txn_frequency_map(db: Session) -> dict[int, float]:
    """Customer id -> transactions/month across observed history (bulk helper)."""
    from datetime import datetime, timezone

    from app.models import Transaction

    rows = db.execute(
        select(
            Transaction.customer_id,
            func.count(),
            func.min(Transaction.created_at),
        ).group_by(Transaction.customer_id)
    ).all()

    def _aware(ts: datetime) -> datetime:
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    out: dict[int, float] = {}
    for customer_id, count, first_ts in rows:
        start = _aware(first_ts if isinstance(first_ts, datetime) else now)
        months = max((now - start).days / 30.0, 0.5)
        out[customer_id] = count / months
    return out
