from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import AppError, NotFoundError
from app.models import RecoveryAction
from app.repositories import opportunity_repository as opp_repo
from app.schemas.common import paged
from app.schemas.recovery import (
    ActionRequest,
    OpportunityDetail,
    OpportunityListItem,
    RecoveryActionOut,
)
from app.utils.formatting import inr
from app.utils.logging_config import agent_logger

logger = agent_logger("recoveryai.api")

router = APIRouter(prefix="/recovery", tags=["recovery"])


def _parse_date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@router.get("/opportunities")
def list_opportunities(
    db: DBSession,
    user: CurrentUser,
    priority: str | None = Query(default=None, examples=["CRITICAL,HIGH"]),
    status_filter: str = Query(default="OPEN,IN_PROGRESS", alias="status"),
    min_amount: float | None = Query(default=None, ge=0),
    customer: str | None = Query(default=None),
    root_cause: str | None = Query(default=None),
    failure_code: str | None = Query(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = Query(default="recovery_score"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    items, total = opp_repo.list_opportunities(
        db,
        priority=priority,
        status=status_filter,
        min_amount=min_amount,
        customer_external_id=customer,
        root_cause=root_cause,
        failure_code=failure_code,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        sort=sort,
        order=order,
        page=page,
        size=size,
    )
    return paged([OpportunityListItem.model_validate(o) for o in items], page=page, size=size, total=total)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def opportunity_detail(db: DBSession, user: CurrentUser, opportunity_id: int) -> OpportunityDetail:
    opp = opp_repo.get_by_id(db, opportunity_id)
    if opp is None:
        raise NotFoundError("OPPORTUNITY_NOT_FOUND", f"Recovery opportunity {opportunity_id} does not exist")
    return OpportunityDetail.model_validate(opp)


@router.get("/status/{transaction_id}")
def recovery_status(db: DBSession, user: CurrentUser, transaction_id: str) -> dict:
    from app.repositories.transaction_repository import get_by_transaction_id

    txn = get_by_transaction_id(db, transaction_id)
    if txn is None:
        raise NotFoundError("TRANSACTION_NOT_FOUND", "Transaction does not exist")
    opp = opp_repo.get_by_transaction(db, txn.id)
    if opp is None:
        raise NotFoundError("OPPORTUNITY_NOT_FOUND", "No recovery opportunity exists for this transaction")
    detail = OpportunityDetail.model_validate(opp)
    payload = detail.model_dump(mode="json")
    payload["expected_recovery_formatted"] = inr(opp.expected_recovery_value)
    payload["revenue_at_risk_formatted"] = inr(opp.revenue_at_risk)
    payload["payment_attempts"] = [
        {
            "attempt_number": a.attempt_number,
            "payment_method": a.payment_method,
            "status": a.status,
            "failure_code": a.failure_code,
            "failure_reason": a.failure_reason,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in txn.attempts
    ]
    return {"success": True, **payload}


@router.post("/opportunities/{opportunity_id}/actions", response_model=RecoveryActionOut)
def create_recovery_action(
    db: DBSession,
    user: CurrentUser,
    opportunity_id: int,
    payload: ActionRequest,
) -> RecoveryActionOut:
    """Simulated recovery action - always gated on explicit human approval."""
    opp = opp_repo.get_by_id(db, opportunity_id)
    if opp is None:
        raise NotFoundError("OPPORTUNITY_NOT_FOUND", f"Recovery opportunity {opportunity_id} does not exist")
    if not payload.approved:
        raise AppError("APPROVAL_REQUIRED", "Customer-affecting actions require human approval")

    result_payload = {
        "simulated": True,
        "note": "Demo mode: no real payment or customer contact was executed.",
        "recommended_action": opp.recommended_action,
        "expected_recovery_value": opp.expected_recovery_value,
    }
    action: RecoveryAction = opp_repo.add_action(
        db,
        opportunity_id=opp.id,
        action_type=payload.action_type.upper(),
        channel=(payload.channel or "").upper() or None,
        status="EXECUTED_SIMULATED",
        approved_by=user.email,
        result=result_payload,
    )
    from datetime import datetime, timezone

    action.executed_at = datetime.now(timezone.utc)
    if opp.status == "OPEN":
        opp.status = "IN_PROGRESS"
    db.commit()
    logger.info("recovery_action_executed", extra={"transaction_id": opp.transaction.transaction_id, "action": action.action_type})
    return RecoveryActionOut.model_validate(action)
