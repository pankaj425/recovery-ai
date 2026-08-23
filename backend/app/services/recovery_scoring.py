"""Deterministic, configurable recovery scoring (0-100) + priority bands.

    recovery_score =
        value_score                 (transaction amount)
      + failure_frequency_score     (attempt count)
      + customer_value_score        (lifetime value)
      + historical_success_score    (past success ratio)
      + probability_score           (ML recovery probability)
      + recency_score               (time decay since failure)

Each component is normalized to 0-1 and multiplied by its configured
weight (weights sum to 100). Breakdowns are persisted for auditability.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import math

from app.core.config import settings
from app.services.failure_classifier import RootCause

RECENCY_DECAY_HOURS = 72.0
RECENCY_FLOOR = 0.5  # even older opportunities keep half recency credit
AMOUNT_LOG_REF = math.log10(60_001)  # amounts >= ~₹60k saturate the value component
LTV_REF = 120_000.0  # INR; lifetime values >= this saturate the customer component
ATTEMPTS_REF = 4


def _amount_norm(amount: float) -> float:
    """Log-scaled so mid-market tickets (₹8k-25k) score meaningfully."""
    return min(math.log10(max(amount, 1.0) + 1) / AMOUNT_LOG_REF, 1.0)


@dataclass(slots=True)
class ScoreComponent:
    name: str
    raw: float  # un-normalized input
    normalized: float  # 0..1
    weight: float
    points: float  # normalized * weight


@dataclass(slots=True)
class RecoveryScore:
    total: float
    priority: str
    components: list[ScoreComponent]

    def breakdown_dict(self) -> dict:
        return {
            "total": round(self.total, 2),
            "priority": self.priority,
            "components": [
                {
                    "name": c.name,
                    "raw": round(c.raw, 4),
                    "normalized": round(c.normalized, 4),
                    "weight": c.weight,
                    "points": round(c.points, 2),
                }
                for c in self.components
            ],
        }


def priority_for_score(score: float) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


def compute_recovery_score(
    *,
    amount: float,
    attempt_count: int,
    lifetime_value: float,
    customer_successes: int,
    customer_failures: int,
    root_cause: RootCause,
    recovery_probability: float,
    hours_since_failure: float,
    weights: dict[str, float] | None = None,
) -> RecoveryScore:
    w = weights or settings.scoring_weights
    total_attempts = max(customer_successes + customer_failures, 1)
    recency_norm = RECENCY_FLOOR + (1 - RECENCY_FLOOR) * math.exp(-hours_since_failure / RECENCY_DECAY_HOURS)

    components_spec = [
        (
            "value",
            amount,
            _amount_norm(amount),
            w["value"],
        ),
        (
            "failure_frequency",
            attempt_count / ATTEMPTS_REF,
            min(attempt_count / ATTEMPTS_REF, 1.0),
            w["failure_frequency"],
        ),
        (
            "customer_value",
            lifetime_value / LTV_REF,
            min(lifetime_value / LTV_REF, 1.0),
            w["customer_value"],
        ),
        (
            "historical_success",
            customer_successes / max(customer_successes + customer_failures, 1),
            customer_successes / total_attempts,
            w["historical_success"],
        ),
        (
            "probability",
            recovery_probability,
            max(0.0, min(1.0, recovery_probability)),
            w["probability"],
        ),
        (
            "recency",
            recency_norm,
            recency_norm,
            w["recency"],
        ),
    ]

    components = [
        ScoreComponent(name=name, raw=raw, normalized=norm, weight=weight, points=norm * weight)
        for name, raw, norm, weight in components_spec
    ]
    total = sum(c.points for c in components)
    total = max(0.0, min(100.0, round(total, 2)))
    return RecoveryScore(total=total, priority=priority_for_score(total), components=components)
