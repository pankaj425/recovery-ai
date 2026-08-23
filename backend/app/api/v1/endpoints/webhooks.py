from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Header, Query, Request, status
from pydantic import ValidationError

from app.api.deps import DBSession
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.webhook import PaymentEventIn, WebhookAck
from app.services import webhook_service

router = APIRouter(prefix="/webhook", tags=["webhooks"])


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    if settings.allow_unsigned_webhooks and not signature:
        return  # dev convenience; disabled in production via env
    if not signature:
        raise AppError("INVALID_SIGNATURE", "Missing X-Signature header", http_status=401)
    expected = hmac.new(settings.webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AppError("INVALID_SIGNATURE", "Webhook signature mismatch", http_status=401)


@router.post(
    "/payment-failed",
    response_model=WebhookAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a payment failure/abandonment event (idempotent)",
)
async def payment_failed_webhook(
    request: Request,
    db: DBSession,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    sync: bool = Query(default=True, description="Process inline (deterministic) vs background queue"),
) -> WebhookAck:
    raw_body = await request.body()
    _verify_signature(raw_body, x_signature)

    try:
        event_in = PaymentEventIn.model_validate_json(raw_body)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        raise AppError(
            "VALIDATION_ERROR",
            f"Invalid webhook payload{f' at {loc}' if loc else ''}: {first.get('msg', 'validation failed')}",
            http_status=422,
        ) from None
    result = webhook_service.ingest_payment_event(db, event_in, defer_processing=not sync)
    return WebhookAck(**result)
