"""Webhook ingestion: signature verification, idempotency, processing pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import Transaction, WebhookEvent
from app.repositories import customer_repository as customer_repo
from app.repositories import transaction_repository as txn_repo
from app.services.opportunity_pipeline import run_recovery_pipeline
from app.schemas.webhook import PaymentEventIn
from app.utils.logging_config import agent_logger

logger = agent_logger("recoveryai.webhook")


def _event_exists(db: Session, event_id: str) -> bool:
    return db.scalar(select(WebhookEvent.id).where(WebhookEvent.event_id == event_id)) is not None


def ingest_payment_event(db: Session, event_in: PaymentEventIn, *, defer_processing: bool = False) -> dict:
    """Idempotent ingestion. Returns an acknowledgement dict."""
    if _event_exists(db, event_in.event_id):
        logger.info("webhook_duplicate", extra={"webhook_id": event_in.event_id, "transaction_id": event_in.transaction_id})
        return {"event_id": event_in.event_id, "duplicate": True, "processed": False, "opportunity_created": False}

    db.add(
        WebhookEvent(
            event_id=event_in.event_id,
            event_type=f"payment.{event_in.status.lower()}",
            payload_json=event_in.model_dump(mode="json"),
            processed=False,
        )
    )
    db.commit()  # persist the ledger entry first (at-least-once semantics)

    if defer_processing:
        from app.workers import webhook_worker

        webhook_worker.enqueue_webhook_event(event_in.model_dump(mode="json"))
        return {
            "event_id": event_in.event_id,
            "duplicate": False,
            "processed": False,
            "opportunity_created": False,
        }

    opportunity_created = process_event(db, event_in)

    event = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_in.event_id))
    if event:
        event.processed = True
        db.commit()

    logger.info(
        "webhook_processed",
        extra={"webhook_id": event_in.event_id, "transaction_id": event_in.transaction_id},
    )
    return {
        "event_id": event_in.event_id,
        "duplicate": False,
        "processed": True,
        "opportunity_created": opportunity_created,
    }


def process_event(db: Session, event_in: PaymentEventIn) -> bool:
    """Apply the event to transaction/customer state and run the recovery pipeline.

    Returns True if a recovery opportunity exists for this transaction afterwards.
    """
    customer = customer_repo.get_or_create(
        db,
        external_customer_id=event_in.customer_id,
        name=None,
        email=None,
    )
    ts = event_in.timestamp or datetime.now(timezone.utc)
    txn = txn_repo.get_by_transaction_id(db, event_in.transaction_id)

    is_success = False  # this endpoint handles failure-side events only

    if txn is None:
        txn = Transaction(
            transaction_id=event_in.transaction_id,
            customer_id=customer.id,
            amount=round(event_in.amount, 2),
            currency=event_in.currency.upper(),
            status=event_in.status,
            payment_method=event_in.payment_method.upper(),
            payment_provider=event_in.payment_provider,
            failure_code=(event_in.failure_code.lower() if event_in.failure_code else None),
            failure_reason=event_in.failure_reason,
            attempt_count=event_in.attempt_number,
            created_at=ts,
        )
        db.add(txn)
        db.flush()
    else:
        txn.status = event_in.status
        txn.attempt_count = max(txn.attempt_count, event_in.attempt_number)
        txn.failure_code = (event_in.failure_code.lower() if event_in.failure_code else txn.failure_code)
        txn.failure_reason = event_in.failure_reason or txn.failure_reason

    txn_repo.add_attempt(
        db,
        txn,
        attempt_number=event_in.attempt_number,
        payment_method=event_in.payment_method.upper(),
        status="FAILED" if not is_success else "SUCCESS",
        failure_code=(event_in.failure_code.lower() if event_in.failure_code else None),
        failure_reason=event_in.failure_reason,
        timestamp=ts,
    )
    # Synthesize earlier attempts when the provider reports attempt_number > 1
    # (each real attempt arrives as its own webhook; gaps mean we missed them).
    existing_attempts = {a.attempt_number for a in txn.attempts}
    for missing in range(1, event_in.attempt_number):
        if missing not in existing_attempts:
            gap_ts = ts - timedelta(minutes=10 * (event_in.attempt_number - missing))
            txn_repo.add_attempt(
                db,
                txn,
                attempt_number=missing,
                payment_method=event_in.payment_method.upper(),
                status="FAILED",
                failure_code=(event_in.failure_code.lower() if event_in.failure_code else None),
                failure_reason="backfilled from provider attempt metadata",
                timestamp=gap_ts,
            )
    customer_repo.recompute_aggregates(db, customer)
    db.flush()

    if event_in.status == "PENDING":
        db.commit()
        return False

    opportunity = run_recovery_pipeline(db, txn)
    db.commit()
    return opportunity is not None
