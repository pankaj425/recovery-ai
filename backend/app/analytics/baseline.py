"""Baseline (rule-based dunning) vs RecoveryAI comparison.

The baseline is the classic "retry everything after 1 hour, same method"
strategy. Its success probability per root cause is an explicit, documented
assumption (configurable via BASELINE_SUCCESS_PROBABILITIES_JSON).

RecoveryAI strategy: pursue opportunities where the model probability clears
a minimum bar; recovered value = amount x probability (expected value).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RecoveryOpportunity

AI_PURSUE_THRESHOLD = 0.25  # pursue when P(recovery) >= 25%


def _split(opportunities: list[RecoveryOption]) -> dict:
    baseline_probs = settings.baseline_success_probabilities
    at_risk = sum(o.amount for o in opportunities)
    baseline_recovered = 0.0
    ai_recovered = 0.0
    pursued = 0
    unnecessary_baseline_retries = 0
    high_value_captured = 0
    high_value_value = 0.0

    for o in opportunities:
        p_base = baseline_probs.get(o.root_cause, 0.15)
        baseline_recovered += o.amount * p_base
        if o.probability >= AI_PURSUE_THRESHOLD:
            ai_recovered += o.expected
            pursued += 1
        if not o.retry_allowed:
            unnecessary_baseline_retries += 1
        if o.amount >= 50_000 or o.lifetime_value >= 100_000:
            high_value_captured += 1
            high_value_value += o.expected

    base_rate = baseline_recovered / at_risk if at_risk else 0.0
    ai_rate = ai_recovered / at_risk if at_risk else 0.0
    improvement = ((ai_rate - base_rate) / base_rate * 100) if base_rate else 0.0
    return {
        "transactions_analyzed": len(opportunities),
        "revenue_at_risk": round(at_risk, 2),
        "baseline_recovery_rate": round(base_rate, 4),
        "ai_assisted_recovery_rate": round(ai_rate, 4),
        "baseline_recovered_revenue": round(baseline_recovered, 2),
        "ai_assisted_recovered_revenue": round(ai_recovered, 2),
        "incremental_recovered_revenue": round(ai_recovered - baseline_recovered, 2),
        "recovery_improvement_pct": round(improvement, 2),
        "opportunities_pursued_by_ai": pursued,
        "unnecessary_baseline_retries": unnecessary_baseline_retries,
        "high_value_opportunities_captured": high_value_captured,
        "high_value_expected_recovery": round(high_value_value, 2),
    }


class RecoveryOption:
    """Lightweight projection used by both analytics and the demo script."""

    __slots__ = ("amount", "root_cause", "probability", "expected", "retry_allowed", "lifetime_value")

    def __init__(
        self,
        *,
        amount: float,
        root_cause: str,
        probability: float,
        expected: float,
        retry_allowed: bool,
        lifetime_value: float,
    ) -> None:
        self.amount = amount
        self.root_cause = root_cause
        self.probability = probability
        self.expected = expected
        self.retry_allowed = retry_allowed
        self.lifetime_value = lifetime_value


def options_from_opportunities(opportunities) -> list[RecoveryOption]:
    return [
        RecoveryOption(
            amount=o.revenue_at_risk,
            root_cause=o.root_cause,
            probability=o.recovery_probability,
            expected=o.expected_recovery_value,
            retry_allowed=bool((o.retry_policy or {}).get("retry_allowed")),
            lifetime_value=o.customer.lifetime_value if o.customer else 0.0,
        )
        for o in opportunities
    ]


def baseline_comparison(db: Session, sample_size: int = 100) -> dict:
    """Compare strategies over the top open opportunities by expected value."""
    stmt = (
        select(RecoveryOpportunity)
        .where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
        .order_by(RecoveryOpportunity.expected_recovery_value.desc())
        .limit(sample_size)
    )
    opportunities = list(db.scalars(stmt).all())
    result = _split(options_from_opportunities(opportunities))
    result["strategy"] = {
        "baseline": "Retry every failure after a fixed interval on the same payment method",
        "recovery_ai": (
            f"Rank by expected recovery value; pursue when P(recovery) >= "
            f"{AI_PURSUE_THRESHOLD:.0%}; smart retry policies; alternative-method escalation"
        ),
    }
    return result


def recovered_revenue_summary(db: Session, days: int | None = None) -> dict:
    """Whole-book view of recoverable revenue under both strategies."""
    stmt = select(RecoveryOpportunity).where(RecoveryOpportunity.status.in_(("OPEN", "IN_PROGRESS")))
    if days is not None:
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(RecoveryOpportunity.created_at >= cutoff)
    opportunities = list(db.scalars(stmt).all())
    return _split(options_from_opportunities(opportunities))
