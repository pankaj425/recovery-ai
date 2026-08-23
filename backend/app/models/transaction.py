from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

STATUSES = ("SUCCESS", "FAILED", "PENDING", "ABANDONED", "REFUNDED")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    status: Mapped[str] = mapped_column(String(16), index=True)  # SUCCESS|FAILED|PENDING|ABANDONED|REFUNDED
    payment_method: Mapped[str] = mapped_column(String(24), index=True)  # CARD|UPI|NETBANKING|WALLET
    payment_provider: Mapped[str] = mapped_column(String(24), default="razorpay")
    failure_code: Mapped[Optional[str]] = mapped_column(String(48), index=True, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer = relationship("Customer", lazy="joined")
    attempts = relationship(
        "PaymentAttempt", back_populates="transaction", order_by="PaymentAttempt.attempt_number",
        cascade="all, delete-orphan",
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16), default="FAILED")
    failure_code: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    transaction = relationship("Transaction", back_populates="attempts")
