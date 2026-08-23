from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PaymentAttemptOut(ORMModel):
    attempt_number: int
    payment_method: str
    status: str
    failure_code: str | None
    failure_reason: str | None
    timestamp: datetime


class CustomerProfile(ORMModel):
    external_customer_id: str
    name: str
    email: str
    segment: str | None
    lifetime_value: float
    successful_transactions: int
    failed_transactions: int


class TransactionRef(ORMModel):
    transaction_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    payment_provider: str
    failure_code: str | None
    failure_reason: str | None
    attempt_count: int
    created_at: datetime


class OpportunityListItem(ORMModel):
    id: int
    customer: CustomerProfile
    transaction: TransactionRef
    revenue_at_risk: float
    recovery_probability: float
    expected_recovery_value: float
    recovery_score: float
    priority: str
    root_cause: str
    sub_cause: str | None
    recommended_action: str
    retry_policy: dict | None
    status: str
    created_at: datetime


class RecoveryActionOut(ORMModel):
    id: int
    action_type: str
    channel: str | None
    status: str
    approved_by: str | None
    result: dict | None
    executed_at: datetime | None


class AIDecisionOut(ORMModel):
    model_version: str
    prediction: dict
    recommendation: dict
    confidence: float
    created_at: datetime


class OpportunityDetail(OpportunityListItem):
    explanation: dict | None
    model_version: str
    updated_at: datetime
    actions: list[RecoveryActionOut]
    decisions: list[AIDecisionOut]


class ActionRequest(BaseModel):
    action_type: str = Field(examples=["UPDATE_PAYMENT_METHOD", "DELAYED_RETRY", "MANUAL_RISK_REVIEW"])
    channel: str | None = Field(default=None, examples=["EMAIL", "SMS", "WHATSAPP", "RETRY", "MANUAL_REVIEW"])
    approved: bool = Field(default=True, description="Human approval - required for customer-affecting actions")
