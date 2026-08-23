from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaymentEventIn(BaseModel):
    """Webhook payload from a simulated provider (Stripe/Razorpay/Adyen shape)."""

    event_id: str = Field(min_length=3, max_length=80, examples=["evt_1001"])
    transaction_id: str = Field(min_length=3, max_length=64, examples=["txn_1001"])
    customer_id: str = Field(min_length=2, max_length=64, examples=["cus_100"])
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", max_length=8)
    payment_method: str = Field(default="CARD", examples=["CARD", "UPI", "NETBANKING", "WALLET"])
    payment_provider: str = Field(default="razorpay", examples=["razorpay", "stripe", "adyen"])
    status: Literal["FAILED", "ABANDONED", "PENDING"] = "FAILED"
    failure_code: str | None = Field(default=None, examples=["insufficient_funds", "expired_card"])
    failure_reason: str | None = None
    attempt_number: int = Field(default=1, ge=1, le=20)
    timestamp: datetime | None = None


class WebhookAck(BaseModel):
    success: bool = True
    event_id: str
    duplicate: bool = False
    processed: bool
    opportunity_created: bool = False
