from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RecoveryOpportunity(Base):
    __tablename__ = "recovery_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)

    revenue_at_risk: Mapped[float] = mapped_column(Float, index=True)
    recovery_probability: Mapped[float] = mapped_column(Float)  # ML prediction [0..1]
    expected_recovery_value: Mapped[float] = mapped_column(Float, index=True)  # risk x probability
    recovery_score: Mapped[float] = mapped_column(Float, index=True)  # 0..100 deterministic
    priority: Mapped[str] = mapped_column(String(12), index=True)  # CRITICAL|HIGH|MEDIUM|LOW
    root_cause: Mapped[str] = mapped_column(String(32))
    sub_cause: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 5-part AI explanation
    retry_policy: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="logreg-v1")

    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)  # OPEN|IN_PROGRESS|RECOVERED|LOST|DISMISSED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transaction = relationship("Transaction", lazy="joined")
    customer = relationship("Customer", lazy="joined")
    actions = relationship("RecoveryAction", back_populates="opportunity", order_by="RecoveryAction.id")
    decisions = relationship("AIDecision", back_populates="opportunity", order_by="AIDecision.id")


class RecoveryAction(Base):
    """Simulated recovery action. Customer-affecting actions require human approval."""

    __tablename__ = "recovery_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("recovery_opportunities.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(48))
    channel: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)  # EMAIL|SMS|WHATSAPP|RETRY|MANUAL_REVIEW
    status: Mapped[str] = mapped_column(String(24), default="PENDING_APPROVAL")  # PENDING_APPROVAL|EXECUTED_SIMULATED|CANCELLED
    approved_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunity = relationship("RecoveryOpportunity", back_populates="actions")


class AIDecision(Base):
    """Immutable audit trail of every prediction + recommendation."""

    __tablename__ = "ai_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("recovery_opportunities.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(32))
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    prediction: Mapped[dict] = mapped_column(JSON)
    recommendation: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opportunity = relationship("RecoveryOpportunity", back_populates="decisions")


class ScoreAudit(Base):
    """Component-level breakdown of the deterministic recovery score (auditability)."""

    __tablename__ = "score_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("recovery_opportunities.id"), index=True)
    components: Mapped[dict] = mapped_column(JSON)  # {"value": {...}, ...}
    weights: Mapped[dict] = mapped_column(JSON)
    total_score: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
