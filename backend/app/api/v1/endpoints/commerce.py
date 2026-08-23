from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.agents.tools import analyze_customer
from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.repositories import customer_repository as customer_repo
from app.repositories.transaction_repository import list_transactions
from app.schemas.common import paged
from app.schemas.recovery import CustomerProfile, TransactionRef

router = APIRouter(tags=["commerce"])


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@router.get("/transactions")
def transactions(
    db: DBSession,
    user: CurrentUser,
    status: str | None = None,
    payment_method: str | None = None,
    failure_code: str | None = None,
    customer: str | None = Query(default=None, alias="customer_id"),
    min_amount: float | None = Query(default=None, ge=0),
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
):
    items, total = list_transactions(
        db,
        status=status,
        payment_method=payment_method,
        failure_code=failure_code,
        customer_external_id=customer,
        min_amount=min_amount,
        search=search,
        date_from=_parse(date_from),
        date_to=_parse(date_to),
        sort=sort,
        order=order,
        page=page,
        size=size,
    )
    return paged([TransactionRef.model_validate(t) for t in items], page=page, size=size, total=total)


@router.get("/transactions/{transaction_id}", response_model=TransactionRef)
def transaction_detail(db: DBSession, user: CurrentUser, transaction_id: str) -> TransactionRef:
    from app.repositories.transaction_repository import get_by_transaction_id

    txn = get_by_transaction_id(db, transaction_id)
    if txn is None:
        raise NotFoundError("TRANSACTION_NOT_FOUND", "Transaction does not exist")
    return TransactionRef.model_validate(txn)


@router.get("/customers")
def customers(
    db: DBSession,
    user: CurrentUser,
    search: str | None = None,
    segment: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
):
    items, total = customer_repo.list_customers(db, search=search, segment=segment, page=page, size=size)
    return paged([CustomerProfile.model_validate(c) for c in items], page=page, size=size, total=total)


@router.get("/customers/{external_customer_id}")
def customer_detail(db: DBSession, user: CurrentUser, external_customer_id: str):
    data = analyze_customer(db, customer_id=external_customer_id)
    if data is None:
        raise NotFoundError("CUSTOMER_NOT_FOUND", "Customer does not exist")
    return {"success": True, "data": data}
